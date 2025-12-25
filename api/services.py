import logging
import json
import boto3
from typing import List, Dict, Union
from decimal import Decimal
import os
from pydantic import BaseModel, Field

import google.generativeai as genai

# Define custom exceptions for the service layer
class DuplicateSignalError(Exception): pass
class StrategyNotFoundError(Exception): pass
class NoSubscribersError(Exception): pass

from api.models import BlogPost, Strategy, Signal, StrategySubscription, UserTrade
from api.includes.bitunix import createBitunixOrder

# Get an instance of a logger for the current module
logger = logging.getLogger(__name__)


def createBlogPost():
    BlogPost.objects.create(title="service", content="this is a test")
    return "ok"


def authenticate(password, auth):
    #secretNum = 86519811531198198131569551651
    #logger.info(f"Password: {password}, Auth: {auth}, Time: {time}")
    #logger.info(f"HASH: {password + str(secretNum * time)}")

    #if auth == password + str(secretNum * time):
    if password == auth:
        return True
    else:
        return False

def getStrategyID(strat_name, auth):
    """Retrieve strategy ID from the database using the Django ORM."""
    try:
        strategy = Strategy.objects.get(name=strat_name)
        if authenticate(strategy.password, auth) == True:
            logger.debug(f"Authentication passed for {strat_name}")
            logger.debug(f"Strategy ID: {strategy.strategy_id} found for {strat_name}")
            return strategy.strategy_id
        else:
            logger.error(f"Authentication failed for {strat_name}")
            return None
    except Strategy.DoesNotExist:
        logger.error(f"Strategy ID not found for {strat_name}")
        return None


def createSignalMessage(data, strategy_id):
    """Create Data Structure for the Signal Message"""
    signalDict = {
            "strategy_id" : strategy_id,
            "symbol" : data['symbol'],
            "side" : data['side'],
            "price" : data['price'],
            "triggertime" : data['time'],
            "tradeSide" : data['tradeSide'],
            "orderType" : None,
            "tpPrice" : None,
            "tpStopType" : None,
            "tpOrderType" : None,
            "tpOrderPrice" : None,
            "slPrice" : None,
            "slStopType" : None,
            "slOrderType" : None,
            "slOrderPrice" : None
        }

    #load optional values if they exist
    if 'orderType' in data:
        signalDict['orderType'] = data['orderType']
    else:
        signalDict['orderType'] = 'MARKET'
    if 'tpPrice' in data:
        signalDict['tpPrice'] = data['tpPrice']
    if 'tpStopType' in data:
        signalDict['tpStopType'] = data['tpStopType']
    if 'tpOrderType' in data:
        signalDict['tpOrderType'] = data['tpOrderType']
    if 'tpOrderPrice' in data:
        signalDict['tpOrderPrice'] = data['tpOrderPrice']
    if 'slPrice' in data:
        signalDict['slPrice'] = data['slPrice']
    if 'slStopType' in data:
        signalDict['slStopType'] = data['slStopType']
    if 'slOrderType' in data:
        signalDict['slOrderType'] = data['slOrderType']
        if data['slOrderType'] == "LIMIT":
            # This seems like a bug, if the stop loss is a LIMIT, the price should likely not be MARKET.
            # For now, correcting the comparison to an assignment. Re-evaluate this logic.
            signalDict['slOrderPrice'] = "MARKET"
        else:
            signalDict['slOrderPrice'] = None

    logger.debug(f"Signal Message: {signalDict}")
    return signalDict

def dupeSignalCheck(signal_message):
    """Checks for a duplicate signal"""
    is_duplicate = Signal.objects.filter(
        symbol=signal_message['symbol'],
        strategy_id=signal_message['strategy_id'],
        side=signal_message['side'],
        tradeSide=signal_message['tradeSide'],
        price=signal_message['price']
    ).exists()

    logger.debug(f"Dupe Check Result: {is_duplicate}")
    return is_duplicate

def addSignalToDB(signal_message):
    """Adds the signal to the database and returns the signal_id"""
    # The 'strategy_id' key in signal_message holds the ID, but the model field is 'strategy'.
    # We create an instance of the Strategy model to assign it.
    strategy_instance = Strategy.objects.get(pk=signal_message['strategy_id'])

    new_signal = Signal.objects.create(
        strategy=strategy_instance,
        symbol=signal_message['symbol'],
        side=signal_message['side'],
        price=signal_message['price'],
        orderType=signal_message['orderType'],
        tpPrice=signal_message['tpPrice'],
        tpStopType=signal_message['tpStopType'],
        tpOrderType=signal_message['tpOrderType'],
        tpOrderPrice=signal_message['tpOrderPrice'],
        slPrice=signal_message['slPrice'],
        slStopType=signal_message['slStopType'],
        slOrderType=signal_message['slOrderType'],
        tradeSide=signal_message['tradeSide']
    )
    logger.debug(f"Signal Added with ID: {new_signal.id}")
    return new_signal.id

def getExchangeList(signal_id):
    """Gets a list of exchanges tied to the strategy being used"""
    try:
        signal = Signal.objects.get(pk=signal_id)
        subscriptions = StrategySubscription.objects.filter(
            strategy=signal.strategy,
            status='Active'
        ).select_related('user_api__exchange')

        exchange_names = {sub.user_api.exchange.name for sub in subscriptions if sub.user_api and sub.user_api.exchange}
        logger.debug(f"Exchange queues to send to: {exchange_names}")
        return list(exchange_names)
    except Signal.DoesNotExist:
        logger.error(f"Signal with ID {signal_id} not found.")
        return []

def findOpenTrade(signal_message):
    """Finds the open trade tied to the signal"""
    closing_side = signal_message['side']
    opening_side = "BUY" if closing_side == "SELL" else "SELL"

    open_trade_signal = Signal.objects.filter(
        symbol=signal_message['symbol'],
        strategy_id=signal_message['strategy_id'],
        side=opening_side,
        tradeSide='OPEN'
    ).order_by('-id').first()

    if open_trade_signal:
        logger.debug(f"Open Trade ID: {open_trade_signal.id} found.")
        return open_trade_signal.id
    
    logger.warning(f"No open trade found for closing signal: {signal_message}")
    return None

def getUserData(strategy, openTradeId):
    """Look up strategy data and get all user API keys, leverage amount and order qty"""
    subscriptions = StrategySubscription.objects.filter(
        strategy_id=strategy,
        status='Active'
    ).select_related('auth_user', 'user_api__exchange')

    user_data_list = []
    if openTradeId != None:
        # For closing trades, fetch associated open trade data
        open_trades = UserTrade.objects.filter(signal_id=openTradeId).select_related('auth_user')
        trades_by_user = {trade.auth_user.id: trade for trade in open_trades}

        for sub in subscriptions:
            if sub.auth_user.id in trades_by_user:
                trade = trades_by_user[sub.auth_user.id]
                user_data_list.append({
                    'api_key': sub.user_api.api_key, 'api_secret': sub.user_api.api_secret,
                    'user_id': sub.auth_user.id, 'name': sub.user_api.exchange.name,
                    'portfolio_percentage': sub.portfolio_percentage, 'leverage_amount': sub.leverage_amount,
                    'max_tp_trades': sub.max_tp_trades, 'enable_sl_trail': sub.enable_sl_trail, 'enable_sms_confirm': sub.enable_sms_confirm,
                    'position_id': trade.position_id, 'trade_qty': trade.trade_qty
                })
    else:
        # For opening trades
        for sub in subscriptions:
            user_data_list.append({
                'api_key': sub.user_api.api_key, 'api_secret': sub.user_api.api_secret,
                'user_id': sub.auth_user.id, 'name': sub.user_api.exchange.name,
                'portfolio_percentage': sub.portfolio_percentage, 'leverage_amount': sub.leverage_amount,
                'max_tp_trades': sub.max_tp_trades, 'enable_sl_trail': sub.enable_sl_trail, 'enable_sms_confirm': sub.enable_sms_confirm
            })

    logger.debug(f"User Data: {user_data_list}")
    return user_data_list

def createTrade(signal_message, user_data, signal_id, exchange_list):
    # Bug fix: Use a dictionary comprehension to avoid all keys sharing the same list reference.
    user_records = {exchange: [] for exchange in exchange_list}
    logger.debug(f"Exchange List: {user_records}")

    for user_item in user_data:
        if user_item['name'] == 'Bitunix':
            # Create the exchange-specific order using the correct user data
            bitunixOrder = createBitunixOrder(signal_message, user_item)
            # Merge the generated order into the user's data payload
            user_item.update(bitunixOrder)
            sendToQueue(user_item, 'Bitunix')
        #if user_data[i]['name'] == 'Coinbase':
        #    user_data[i].update(coinbaseOrder)
        #    sendToQueue(user_data[i], 'Coinbase')
    return user_records

def sendToQueue(user_trade, exchange_name):
    logger.debug(f"Send to Queue: {user_trade}")

    if user_trade["name"] == 'Bitunix':
        # Boto3 will automatically find credentials from environment variables.
        # Removed commented-out keys for security hygiene.
        client = boto3.client('sqs', region_name='us-east-1')
        response = client.send_message(
            QueueUrl=f"https://sqs.us-east-1.amazonaws.com/531367011239/{user_trade['name']}_Queue",
            MessageBody=json.dumps(user_trade)
        )
        logger.debug(f"Send to Queue Response: {response}")

def processTradingViewSignal(data):
    try:
        strategy_id = getStrategyID(data['strategy'], data['auth'])
        if strategy_id == None:
            raise StrategyNotFoundError(f"Strategy '{data['strategy']}' not found.")

        signal_message = createSignalMessage(data, strategy_id)

        if not dupeSignalCheck(signal_message):
            signal_id = addSignalToDB(signal_message)
            exchange_list = getExchangeList(signal_id)
            if signal_message['tradeSide'] == 'CLOSE':
                openTradeId = findOpenTrade(signal_message)
            else:
                openTradeId = None
            user_data = getUserData(signal_message['strategy_id'], openTradeId)
            if not user_data:
                raise NoSubscribersError(f"No active user subscriptions found for strategy_id: {signal_message['strategy_id']}. Halting trade creation.")

            createTrade(signal_message, user_data, signal_id, exchange_list)
        else:
            raise DuplicateSignalError("Duplicate signal found. Ignoring.")

    except (StrategyNotFoundError, DuplicateSignalError, NoSubscribersError) as e:
        # Re-raise known exceptions to be handled by the view
        raise e
    except Exception as e:
        # Log and re-raise any unexpected exceptions
        logger.error(f"An unexpected error occurred in processTradingViewSignal: {e}", exc_info=True)
        raise



#######################################################################################################

# --- 1. Pydantic Schemas for Structured Output ---

# Defines the structure for a single Take Profit (TP) entry
class HRJTakeProfitTradesSchema(BaseModel):
    """Corresponds to the HRJTakeProfitTrades model."""
    series_num: int = Field(..., description="The sequential number of the take-profit target (e.g., 1, 2, 3...).")
    tp_price: float = Field(..., description="The price at which to take profit.")

# Defines the main trade signal structure, nesting the TP list
class HRJDiscordSignalsSchema(BaseModel):
    """Corresponds to the HRJDiscordSignals model."""
    asset: str = Field(..., description="The cryptocurrency asset pair (e.g., 'LINK/USDT').")
    trade_type: str = Field(..., description="The trade direction, must be 'long' or 'short' in lowercase.")
    leverage: int = Field(..., description="The leverage multiplier (e.g., 5).")
    balance: float = Field(..., description="The percentage of capital allocated (e.g., 3.00 for 3%).")
    entry_price: float = Field(..., description="The price to enter the trade.")
    entry_order_type: str = Field(..., description="The order type, must be 'market' or 'limit' in lowercase.")
    stop_loss: float = Field(..., description="The stop-loss price.")
    # Renaming this field to match the original model structure is complex with Pydantic
    # so we keep it as a list of TP schemas
    take_profits: List[HRJTakeProfitTradesSchema] = Field(..., description="A list of take-profit targets.")


def create_gemini_prompt(signal_message: str) -> str:
    """
    Creates a highly structured prompt for the Gemini API to parse a trade signal message.
    """
    # The prompt is simplified because the Pydantic schema will handle the output format.
    prompt = f"""You are an expert API endpoint for a trading bot. Your task is to analyze a plain text message and determine if it is a complete trade signal.

If the message is a trade signal, you MUST extract the necessary values and return a minified JSON object that strictly adheres to the provided schema. The JSON output will be validated against the schema.

If the message is NOT a complete trade signal (e.g., it's a trade update like 'TP hit', a general comment, or missing critical data), you MUST respond with the single word: false

**Extraction Rules:**
1. Extract numerical values only (e.g., 5 from '5X', 3.00 from '3% of capital').
2. The 'trade_type' must be lowercase.
3. The 'entry_order_type' must be lowercase and inferred from the text (e.g., 'limit order' -> 'limit', 'market' -> 'market').

---

**Message to process:**
{signal_message}
"""
    return prompt

def call_gemini_api(prompt: str) -> Union[str, Dict]:
    """
    Calls the Gemini API with a given prompt, enforcing Pydantic-based JSON output.

    Args:
        prompt: The prompt to send to the Gemini API.

    Returns:
        The text response (JSON string or 'false'), or an error message string.
    """
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return "Error: GEMINI_API_KEY not found in environment variables."

        # Configure once globally or within the function if preferred
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel('gemini-2.5-flash')

        # 1. Define the desired output structure using the Pydantic schema
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=HRJDiscordSignalsSchema,
        )

        response = model.generate_content(
            contents=prompt,
            generation_config=generation_config,
        )

        response_text = response.text.strip()
        
        # 2. Handle the 'false' non-signal case separately
        if response_text.lower() == "false":
             return "false"

        # 3. For a successful JSON response, parse it and return the required format
        try:
            parsed_data = json.loads(response_text)
            
            # Restructure the 'take_profits' list to match the two-model Django structure
            take_profits_data = parsed_data.pop("take_profits", [])
            
            final_json = {
                "HRJDiscordSignals": parsed_data,
                "HRJTakeProfitTrades": take_profits_data
            }
            
            # Return the final JSON as a string for minification/transfer purposes
            return json.dumps(final_json) 
            
        except json.JSONDecodeError:
            # This should rarely happen with response_schema, but is a robust fallback
            return f"Error: Failed to decode JSON from API response: {response_text}"

    except Exception as e:
        return f"An unexpected error occurred while calling the Gemini API: {e}"
            
    
       
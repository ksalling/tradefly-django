import os
import json
import logging
import google.generativeai as genai
from google.generativeai.types import generation_types
from django.db import transaction

from api.models import Strategy, HRJDiscordSignal, HRJTakeProfitTrade, FJDiscordSignal, FJTakeProfitTrade, SIGSCANDiscordSignal, SIGSCANTakeProfitTrade, StrategySubscription, UserApi
import boto3
#from dotenv import load_dotenv

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
#load_dotenv()
logger = logging.getLogger(__name__)

api_key = os.getenv('GEMINI_API_KEY')
#if api_key:
genai.configure(api_key=api_key)
#else:
#logger.warning("GEMINI_API_KEY not found in environment variables. API calls will fail.")

# -------------------------------------------------------------------------
# PROMPT TEMPLATES
# -------------------------------------------------------------------------

HRJ_TEMPLATE = """
You are a trading signal parser. Your goal is to extract structured JSON data from Discord messages based on specific Django models.

### INSTRUCTIONS:
1. Analyze the "INPUT MESSAGE" below.
2. Determine if it is a valid trading signal based on the examples provided.
3. If it is NOT a signal (e.g., status updates, chat, target hit notifications), output exactly the string: "false".
4. If it IS a signal, output valid JSON matching the schema below.
5. Do not include markdown formatting (like ```json) in your response.

### DJANGO MODELS REFERENCE:
class HRJDiscordSignals(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, db_column='strategy_id', blank=True, null=True)
    asset = models.CharField(max_length=255)
    trade_type = models.CharField(max_length=5, choices=[('long', 'Long'), ('short', 'Short')])
    leverage = models.IntegerField(default=1)
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    entry_price = models.DecimalField(max_digits=20, decimal_places=10)
    entry_order_type = models.CharField(max_length=6, choices=[('market', 'Market'), ('limit', 'Limit')])
    stop_loss = models.DecimalField(max_digits=20, decimal_places=10)
class HRJTakeProfitTrades(models.Model):
    signal = models.ForeignKey(HRJDiscordSignals, on_delete=models.CASCADE, db_column='signal_id')
    series_num = models.IntegerField(default=1)
    tp_price = models.DecimalField(max_digits=20, decimal_places=10)

### FEW-SHOT EXAMPLES:

Example 1 (Signal):
Input:
LINK/USDT (LONG)
Leverage: 5X 
Balance: 3% of capital
Entry: 12.32 - (limit order)
TP1: 14.92
TP2: 18.73
TP3: 24.16
TP4: 31.87
SL: 9.89
R:R: 8

Output:
{
  "HRJDiscordSignals": {
    "asset": "LINK/USDT",
    "trade_type": "long",
    "leverage": 5,
    "balance": 3.00,
    "entry_price": 12.32,
    "entry_order_type": "limit",
    "stop_loss": 9.89
  },
  "HRJTakeProfitTrades": [
    { "series_num": 1, "tp_price": 14.92 },
    { "series_num": 2, "tp_price": 18.73 },
    { "series_num": 3, "tp_price": 24.16 },
    { "series_num": 4, "tp_price": 31.87 }
  ]
}

Example 2 (Non-Signal):
Input:
✅  The first target of this BTC/USDT was reached @Brigade ⚔️

Output:
false

### INPUT MESSAGE TO PROCESS:
"""

FJ_TEMPLATE = """
You are a trading signal parser. Your goal is to extract structured JSON data from Discord messages based on specific Django models.
Note: Inputs may use commas (,) for decimals. You must convert these to dots (.) for the JSON output.

### INSTRUCTIONS:
1. Analyze the "INPUT MESSAGE" below.
2. Determine if it is a valid trading signal based on the examples provided.
3. If it is NOT a signal (e.g., status updates, chat, target hit notifications), output exactly the string: "false".
4. If it IS a signal, output valid JSON matching the schema below.
5. Do not include markdown formatting (like ```json) in your response.

### DJANGO MODELS REFERENCE:
class FJDiscordSignals(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, db_column='strategy_id', blank=True, null=True)
    asset = models.CharField(max_length=255)
    trade_type = models.CharField(max_length=5, choices=[('long', 'Long'), ('short', 'Short')])
    entry_price = models.DecimalField(max_digits=20, decimal_places=10)
    entry_order_type = models.CharField(max_length=6, choices=[('market', 'Market'), ('limit', 'Limit')])
    stop_loss = models.DecimalField(max_digits=20, decimal_places=10)
class FJTakeProfitTrades(models.Model):
    signal = models.ForeignKey(FJDiscordSignals, on_delete=models.CASCADE, db_column='signal_id')
    series_num = models.IntegerField()
    tp_price = models.DecimalField(max_digits=20, decimal_places=10)

### FEW-SHOT EXAMPLES:

Example 1 (Signal):
Input:
SOL/USDT (long) 12h chart 
Entry: 127,70 - (limit long)
TP1: 134,66
TP2: 143,16
TP3: 155,97
TP4: 180,23
TP5: 200,41
TP6: 224,49
TP7: 261,90
SL: 114,04
R:R: 10,07

Output:
{
  "FJDiscordSignals": {
    "asset": "SOL/USDT",
    "trade_type": "long",
    "entry_price": 127.70,
    "entry_order_type": "limit",
    "stop_loss": 114.04
  },
  "FJTakeProfitTrades": [
    { "series_num": 1, "tp_price": 134.66 },
    { "series_num": 2, "tp_price": 143.16 },
    { "series_num": 3, "tp_price": 155.97 },
    { "series_num": 4, "tp_price": 180.23 },
    { "series_num": 5, "tp_price": 200.41 },
    { "series_num": 6, "tp_price": 224.49 },
    { "series_num": 7, "tp_price": 261.90 }
  ]
}

Example 2 (Non-Signal):
Input:
TP 1 was reached @Brigade ⚔️

Output:
false

### INPUT MESSAGE TO PROCESS:
"""

SIGSCAN_TEMPLATE = """
You are a trading signal parser. Your goal is to extract structured JSON data from Discord messages based on specific Django models.
Note: Inputs may use commas (,) for decimals. You must convert these to dots (.) for the JSON output.

### INSTRUCTIONS:
1. Analyze the "INPUT MESSAGE" below.
2. Determine if it is a valid trading signal based on the examples provided.
3. If it is NOT a signal (e.g., status updates, chat, target hit notifications), output exactly the string: "false".
4. If it IS a signal, output valid JSON matching the schema below.
5. Do not include markdown formatting (like ```json) in your response.

### DJANGO MODELS REFERENCE:
class SIGSCANDiscordSignals(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, db_column='strategy_id', blank=True, null=True)
    asset = models.CharField(max_length=255)
    trade_type = models.CharField(max_length=5, choices=[('long', 'Long'), ('short', 'Short')])
    entry_price = models.DecimalField(max_digits=20, decimal_places=10)
    entry_order_type = models.CharField(max_length=6, choices=[('market', 'Market'), ('limit', 'Limit')])
    stop_loss = models.DecimalField(max_digits=20, decimal_places=10)
class SIGSCANTakeProfitTrades(models.Model):
    signal = models.ForeignKey(SIGSCANDiscordSignals, on_delete=models.CASCADE, db_column='signal_id')
    series_num = models.IntegerField()
    tp_price = models.DecimalField(max_digits=20, decimal_places=10)

### FEW-SHOT EXAMPLES:

VIRTUAL/USDT 4h (SHORT)  |  Confluence 76/100  |  R:R 3.87
Reasons: Supply anchored at swing high; Supply reaction + reject; Liquidity sweep (buy-side) + reject; Structure weakening (close < EMA50); Compression (BBW low); Displacement present

VIRTUAL/USDT (SHORT)
Leverage: 5X
Risk (Entry→SL): 0.9%  |  Suggested: 6X
Entry: 0.722 (limit order)
TP1: 0.697
TP2: 0.693
TP3: 0.689
TP4: 0.688
SL: 0.728
R:R: 3.87

Image: tradefly_out/VIRTUAL_USDT_4h_SHORT.png

Output:
{
  "SIGSCANDiscordSignals": {
    "asset": "VIRTUALUSDT",
    "trade_type": "short",
    "entry_price": 0.722,
    "entry_order_type": "limit",
    "stop_loss": 0.728
  },
  "SIGSCANTakeProfitTrades": [
    { "series_num": 1, "tp_price": 0.697 },
    { "series_num": 2, "tp_price": 0.693 },
    { "series_num": 3, "tp_price": 0.689 },
    { "series_num": 4, "tp_price": 0.688 }
  ]
}

Example 2 (Non-Signal):
Input:
TP 1 was reached @Brigade ⚔️

Output:
false

### INPUT MESSAGE TO PROCESS:
"""

# -------------------------------------------------------------------------
# FUNCTIONS
# -------------------------------------------------------------------------

def generate_prompt(signal_type: str, message_content: str) -> str:
    """
    Generates the appropriate prompt based on the signal type (HRJ or FJ).
    """
    if signal_type.upper() == "HRJ":
        return HRJ_TEMPLATE + f"\n{message_content}"
    elif signal_type.upper() == "FJ":
        return FJ_TEMPLATE + f"\n{message_content}"
    elif signal_type.upper() == "SIGSCAN":
        return SIGSCAN_TEMPLATE + f"\n{message_content}"
    else:
        raise ValueError("Invalid signal_type. Must be 'HRJ' or 'FJ' or 'SIGSCAN'.")

def call_gemini_api(prompt: str):
    """
    Calls the Gemini API with a given prompt and returns the cleaned response.

    Args:
        prompt: The prompt to send to the Gemini API.

    Returns:
        A dictionary from the parsed JSON, the string "false", or None on error.
    """
    if not api_key:
        logger.error("GEMINI_API_KEY not found.")
        return None

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean up potential markdown fences that the LLM might add despite instructions
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```"):
             response_text = response_text[3:-3].strip()

        if response_text.lower() == "false":
            logger.info("Gemini API call returned 'false'.")
            return "false"

        # Attempt to parse the cleaned text as JSON
        return json.loads(response_text)

    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from Gemini API response: {response_text}")
        return None
    except generation_types.BlockedPromptError as e:
        logger.error(f"Gemini API call blocked due to a prompt safety issue: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while calling the Gemini API: {e}", exc_info=True)
        return None

@transaction.atomic
def save_signal_from_gemini_response(signal_data: dict, signal_type: str):
    """
    Saves the parsed signal data from Gemini into the appropriate Django models.

    Args:
        signal_data: The dictionary containing the parsed signal data.
        signal_type: The type of signal ('HRJ' or 'FJ').

    Returns:
        The created signal object or None on error.
    """
    try:
        # Look up the strategy by name
        strategy = Strategy.objects.get(name=signal_type.upper())
    except Strategy.DoesNotExist:
        logger.error(f"No strategy found linked to a SignalTrigger with name='{signal_type.lower()}''.")
        return None

    try:
        if signal_type.upper() == "HRJ":
            main_signal_data = signal_data.get("HRJDiscordSignals", {})
            take_profit_data = signal_data.get("HRJTakeProfitTrades", [])

            if not main_signal_data:
                raise ValueError("HRJDiscordSignals key not found in response.")

            signal = HRJDiscordSignal.objects.create(strategy=strategy, **main_signal_data)

            for tp in take_profit_data:
                HRJTakeProfitTrade.objects.create(signal=signal, **tp)
            
            logger.info(f"Successfully created HRJ Signal {signal.id} for strategy '{strategy.name}'.")
            return strategy, signal

        elif signal_type.upper() == "FJ":
            main_signal_data = signal_data.get("FJDiscordSignals", {})
            take_profit_data = signal_data.get("FJTakeProfitTrades", [])

            if not main_signal_data:
                raise ValueError("FJDiscordSignals key not found in response.")

            signal = FJDiscordSignal.objects.create(strategy=strategy, **main_signal_data)

            for tp in take_profit_data:
                FJTakeProfitTrade.objects.create(signal=signal, **tp)

            logger.info(f"Successfully created FJ Signal {signal.id} for strategy '{strategy.name}'.")
            return strategy, signal

        elif signal_type.upper() == "SIGSCAN":
            main_signal_data = signal_data.get("SIGSCANDiscordSignals", {})
            take_profit_data = signal_data.get("SIGSCANTakeProfitTrades", [])

            if not main_signal_data:
                raise ValueError("SIGSCANDiscordSignals key not found in response.")

            signal = SIGSCANDiscordSignal.objects.create(strategy=strategy, **main_signal_data)

            for tp in take_profit_data:
                SIGSCANTakeProfitTrade.objects.create(signal=signal, **tp)

            logger.info(f"Successfully created SIGSCAN Signal {signal.id} for strategy '{strategy.name}'.")
            return strategy, signal

    except Exception as e:
        logger.error(f"Error saving signal data to database: {e}", exc_info=True)
        # The @transaction.atomic decorator will automatically roll back the transaction on exception.
        return None

def format_bitunix_payload(signal, user_api, subscription):
    """
    Formats the order payload for BitUnix batch orders.
    API Reference: https://openapidoc.bitunix.com/doc/trade/batch_order.html
    """
    # 1. Symbol Mapping
    # BitUnix uses standard symbols without '/' usually, e.g. BTCUSDT
    symbol = signal.asset.replace('/', '').upper()
    
    # 2. Side Mapping
    # Signal trade_type is 'long' or 'short'
    # BitUnix uses 'BUY' or 'SELL' in the side field
    side = 'BUY' if signal.trade_type.lower() == 'long' else 'SELL'
    
    # 3. Quantity Placeholder
    # We do not have user balance here to calculate position size.
    # We will use a placeholder or derived value.
    # If subscription has portfolio_percentage, we pass that for the consumer to handle.
    # But batch order requires 'qty'. We'll use a string placeholder "{qty}" to indicate
    # the consumer must fill this.
    qty_placeholder = "{qty}" 
    
    # 4. Entry Order
    entry_order = {
        "side": side,
        "price": str(signal.entry_price),
        "qty": qty_placeholder,
        "orderType": "LIMIT",
        "reduceOnly": False,
        "effect": "GTC",
        # Including SL in the main order directly if supported by BitUnix for the position
        # The docs show 'slPrice', 'slStopType', 'slOrderType' in the order object.
        "slPrice": str(signal.stop_loss),
        "slStopType": "MARK", # Assuming MARK price for triggers is standard/safer
        "slOrderType": "MARKET" # Market stop is standard for SL
    }
    
    orders = [entry_order]
    
    # 5. Take Profit Orders
    # We need to find the TP trades associated with this signal.
    # The signal object passed here is the Django model instance.
    # We need to access the related TakeProfitTrade objects.
    
    # Determine the reverse side for TPs
    tp_side = 'SELL' if side == 'BUY' else 'BUY'
    
    # Access TPs based on signal type
    # We can try to dynamically get the related manager or check the type
    tps = []
    if isinstance(signal, HRJDiscordSignal):
        tps = list(signal.hrjtakeprofittrade_set.all())
    elif isinstance(signal, FJDiscordSignal):
        tps = list(signal.fjtakeprofittrade_set.all())
    elif isinstance(signal, SIGSCANDiscordSignal):
        tps = list(signal.sigscantakeprofittrade_set.all())
        
    # Sort TPs by price? Usually good to be ordered.
    tps.sort(key=lambda x: x.series_num)
    
    num_tps = len(tps)
    if num_tps > 0:
        # We need to split the entry quantity among TPs.
        # Since we use a placeholder for total qty, we can express TP qty as fraction?
        # BitUnix requires absolute number.
        # We'll use a string "{qty_tp_1}", "{qty_tp_2}" etc or "{qty} * 0.25"
        # Let's use a clear placeholder string the consumer can parse.
        # E.g. "25%"
        
        # Determine split (equal split for simplicity unless specified)
        # If 4 TPs, 25% each.
        percentage = 1.0 / num_tps
        
        for i, tp in enumerate(tps):
            tp_order = {
                "side": tp_side,
                "price": str(tp.tp_price),
                "qty": f"{{qty}} * {percentage:.2f}", # Placeholder expression
                "orderType": "LIMIT",
                "reduceOnly": True, # Important for TP to close position
                "effect": "GTC"
            }
            orders.append(tp_order)

    # 6. Construct Final Payload
    payload = {
        "symbol": symbol,
        "orderList": orders,
        # API requires nonce, timestamp, sign, api-key in HEADERS, not body usually?
        # The doc shows --data '{"symbol":..., "orderList":...}'
        # So the body is just symbol and orderList.
    }
    
    return payload

def format_default_payload(signal, user_api, subscription):
    """
    Generic payload format for unspecified exchanges.
    """
    return {
        "strategy": signal.strategy.name if signal.strategy else "Unknown",
        "signal_id": signal.id,
        "user_api_valid": bool(user_api),
        "order": {
            "asset": signal.asset,
            "side": signal.trade_type.upper(),
            "type": signal.entry_order_type.upper(),
            "price": str(signal.entry_price),
            "stop_loss": str(signal.stop_loss),
            "leverage": getattr(signal, 'leverage', 1)
        }
    }

def process_and_dispatch_signal(strategy, signal_obj):
    """
    Looks up active strategy subscriptions, fetches UserApi info, formats orders,
    and dispatches them to the user's SQS queue.
    """
    logger.info(f"Processing signal dispatch for strategy: {strategy.name}, Signal ID: {signal_obj.id}")

    try:
        subscriptions = StrategySubscription.objects.filter(strategy=strategy, status='Active')
        
        if not subscriptions.exists():
            logger.info(f"No active subscriptions found for strategy '{strategy.name}'.")
            return

        sqs = boto3.client('sqs', region_name='us-east-1')

        for sub in subscriptions:
            try:
                user_api = sub.user_api
                if not user_api:
                    logger.warning(f"Subscription {sub.id} has no linked UserApi. Skipping.")
                    continue

                # Determine formatting function based on exchange
                exchange_name = user_api.exchange.name.lower() if user_api.exchange and user_api.exchange.name else ""
                
                if "bitunix" in exchange_name:
                    order_payload = format_bitunix_payload(signal_obj, user_api, sub)
                else:
                    order_payload = format_default_payload(signal_obj, user_api, sub)
                
                # Wrap in the dispatch envelope
                payload = {
                    "strategy": strategy.name,
                    "signal_id": signal_obj.id,
                    "user_api": {
                        "api_key": user_api.api_key,
                        "api_secret": user_api.api_secret,
                        "exchange": user_api.exchange.name if user_api.exchange else None,
                        "name": user_api.name
                    },
                    "order_message": order_payload
                }

                # Construct Queue URL
                queue_name_suffix = user_api.name if user_api.name else f"user_{user_api.auth_user.id}"
                queue_url = f"https://sqs.us-east-1.amazonaws.com/531367011239/{queue_name_suffix}_Queue"

                logger.info(f"Sending order to SQS: {queue_url}")
                
                response = sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(payload)
                )
                
                logger.info(f"Message sent to SQS for user {user_api.name}. MessageId: {response.get('MessageId')}")

            except Exception as e:
                logger.error(f"Error processing subscription {sub.id}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in process_and_dispatch_signal: {e}", exc_info=True)

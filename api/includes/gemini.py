import os
import json
import logging
import google.generativeai as genai
from google.generativeai.types import generation_types
from django.db import transaction

from api.models import Strategy, HRJDiscordSignal, HRJTakeProfitTrade, FJDiscordSignal, FJTakeProfitTrade, SIGSCANDiscordSignal, SIGSCANTakeProfitTrade
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
        # Look up the strategy using the new ForeignKey relationship.
        strategy = Strategy.objects.get(signal_trigger__name=signal_type.lower())
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
            return signal

        elif signal_type.upper() == "FJ":
            main_signal_data = signal_data.get("FJDiscordSignals", {})
            take_profit_data = signal_data.get("FJTakeProfitTrades", [])

            if not main_signal_data:
                raise ValueError("FJDiscordSignals key not found in response.")

            signal = FJDiscordSignal.objects.create(strategy=strategy, **main_signal_data)

            for tp in take_profit_data:
                FJTakeProfitTrade.objects.create(signal=signal, **tp)

            logger.info(f"Successfully created FJ Signal {signal.id} for strategy '{strategy.name}'.")
            return signal
            
        elif signal_type.upper() == "SIGSCAN":
            main_signal_data = signal_data.get("SIGSCANDiscordSignals", {})
            take_profit_data = signal_data.get("SIGSCANTakeProfitTrades", [])

            if not main_signal_data:
                raise ValueError("SIGSCANDiscordSignals key not found in response.")

            signal = SIGSCANDiscordSignal.objects.create(strategy=strategy, **main_signal_data)

            for tp in take_profit_data:
                SIGSCANTakeProfitTrade.objects.create(signal=signal, **tp)

            logger.info(f"Successfully created SIGSCAN Signal {signal.id} for strategy '{strategy.name}'.")
            return signal

    except Exception as e:
        logger.error(f"Error saving signal data to database: {e}", exc_info=True)
        # The @transaction.atomic decorator will automatically roll back the transaction on exception.
        return None

import os
import json
import logging
import time
import hashlib
import uuid
import requests
from api.models import UserApi
from .open_api_http_sign import get_auth_headers, sort_params
from .open_api_http_future_private import OpenApiHttpFuturePrivate



# Configure logging
logger = logging.getLogger(__name__)

def createBitunixOrder(signal_message, user_data_item):
    """
    Creates a Bitunix-specific order payload based on the signal and user data.
    """
    # Determine if this is a closing trade to set reduceOnly and get positionId
    is_closing_trade = signal_message.get('tradeSide') == 'CLOSE'
    position_id = user_data_item.get('position_id') if is_closing_trade else None
    
    # TODO: Trade quantity calculation logic is needed here for opening trades.
    # For now, using the quantity from the closing trade if available.
    trade_qty = user_data_item.get('trade_qty') # This will be None for opening trades

    # Start with a base order structure
    order = {
        "symbol": f"{signal_message['symbol']}",
        "orderList": [
            {
                "side": signal_message['side'],  # Dynamically set from signal
                "price": f"{signal_message['price']}",
                "qty": trade_qty,  # Will be None for open trades until qty calculation is added
                "orderType": f"{signal_message['orderType']}",
                "reduceOnly": "true" if is_closing_trade else "false",
                "effect": "GTC",
                "clientId": "tradeFlyBot",
                "positionId": position_id
            }
        ]
    }

    # Conditionally add Take Profit and Stop Loss details to the first order in the list
    order_details = order["orderList"][0]

    if signal_message['tpPrice'] != None and signal_message['slPrice'] == None:
        logger.info('Adding Take Profit details to the order.')
        order_details.update({
            "tpPrice": f"{signal_message['tpPrice']}",
            "tpStopType": f"{signal_message['tpStopType']}",
            "tpOrderType": f"{signal_message['tpOrderType']}",
            "tpOrderPrice": f"{signal_message['tpOrderPrice']}"
        })
    elif signal_message['slPrice'] != None:
        logger.info('Adding Stop Loss details to the order.')
        order_details.update({
            "slPrice": f"{signal_message['slPrice']}",
            "slStopType": f"{signal_message['slStopType']}",
            "slOrderType": f"{signal_message['slOrderType']}",
            "slOrderPrice": f"{signal_message['slOrderPrice']}"
        })

    return order

def _handle_response(response: requests.Response) -> Dict[str, Any]:
        """
        Handle response
        
        Args:
            response: Response object
            
        Returns:
            Dict[str, Any]: Response data
            
        Raises:
            Exception: When response status code is not 200 or business status code is not 0
        """
        if response.status_code != 200:
            raise Exception(f"HTTP Error: {response.status_code}")
        
        data = response.json()
        if data["code"] != 0:
            error = ErrorCode.get_by_code(data["code"])
            if error:
                raise Exception(str(error))
            raise Exception(f"Unknown Error: {data['code']} - {data['msg']}")
        
        return data["data"]


def get_account(user_api_id, margin_coin: str = "USDT") -> Dict[str, Any]:
    """
    Retrieves account information from Bitunix for a specific UserApi credential.
    """
    try:
        user_api = UserApi.objects.get(id=user_api_id)
    except UserApi.DoesNotExist:
        logger.error(f"UserApi with id {user_api_id} not found.")
        return {"error": "UserApi credentials not found."}

    api_key = user_api.api_key
    secret_key = user_api.api_secret

    if not api_key or not secret_key:
        return {"error": "API Key or Secret is missing for this user."}

    # Bitunix API Configuration
    base_url = "https://fapi.bitunix.com"
    url = f"{base_url}/api/v1/futures/account"
    params = {
        "marginCoin": margin_coin
    }

    query_string = sort_params(params)
    headers = get_auth_headers(api_key, secret_key, query_string)

    response = requests.get(url, params=params, headers=headers)

    return _handle_response(response)

def get_account_history(user_api_id, symbol = None) -> Dict[str, Any]:
    """
    Retrieves account information from Bitunix for a specific UserApi credential.
    """
    try:
        user_api = UserApi.objects.get(id=user_api_id)
    except UserApi.DoesNotExist:
        logger.error(f"UserApi with id {user_api_id} not found.")
        return {"error": "UserApi credentials not found."}

    api_key = user_api.api_key
    secret_key = user_api.api_secret

    if not api_key or not secret_key:
        return {"error": "API Key or Secret is missing for this user."}

    """
    Get historical position information
    
    Args:
        symbol: Trading pair, if not provided, get all positions
        
    Returns:
        Dict[str, Any]: Historical position information
    """
     # Bitunix API Configuration
    base_url = "https://fapi.bitunix.com"
    #url = f"{base_url}/api/v1/futures/account"
    url = f"{base_url}/api/v1/futures/position/get_history_positions"
    #url = f"{base_url}/api/v1/futures/trade/get_history_orders"

    params = {}
    if symbol:
        params["symbol"] = symbol
        
    query_string = sort_params(params)
    headers = get_auth_headers(api_key, secret_key, query_string)
    
    response = requests.get(url, params=params, headers=headers)
    return _handle_response(response)


def test_account_class(user_api_id):
    """
    Retrieves account information from Bitunix for a specific UserApi credential.
    """
    try:
        user_api = UserApi.objects.get(id=user_api_id)
    except UserApi.DoesNotExist:
        logger.error(f"UserApi with id {user_api_id} not found.")
        return {"error": "UserApi credentials not found."}

    api_key = user_api.api_key
    secret_key = user_api.api_secret

    if not api_key or not secret_key:
        return {"error": "API Key or Secret is missing for this user."}

    # Bitunix API Configuration
    base_url = "https://fapi.bitunix.com"
    url = f"{base_url}/api/v1/futures/account"
    params = {
        "marginCoin": margin_coin
    }


    client = OpenApiHttpFuturePrivate(config)
    
    try:
        # Get account information
        account = client.get_account()
        logging.info(f"Account info: {account}")
        
        # Get historical position information
        history_positions = client.get_history_positions("BTCUSDT")
        logging.info(f"History positions: {history_positions}")
        
        # Get historical orders
        history_orders = client.get_history_orders("BTCUSDT")
        logging.info(f"History orders: {history_orders}")

    except Exception as e:
        logging.error(f"Error in main: {e}")
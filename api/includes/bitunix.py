import os
import json
import logging

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
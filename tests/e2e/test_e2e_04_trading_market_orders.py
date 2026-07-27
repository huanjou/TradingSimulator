import requests
from conftest import API_GATEWAY_URL, wait_for_balance, wait_for_order_status


def test_market_buy_and_sell_order_flow(new_user_factory):
    # 1. Setup user with initial 25,000 USD balance
    user = new_user_factory(deposit_usd=25000.0)
    headers = user["headers"]
    user_id = user["user_id"]

    # 2. Place BUY Market order for 0.5 ETH/USD
    buy_payload = {
        "symbol": "ETH/USD",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.5,
    }
    resp = requests.post(
        f"{API_GATEWAY_URL}/orders/", json=buy_payload, headers=headers
    )
    assert resp.status_code == 202, f"Failed to place BUY market order: {resp.text}"
    buy_order = resp.json()
    buy_id = buy_order["id"]

    # 3. Poll order status until FILLED
    filled_buy = wait_for_order_status(
        headers, buy_id, ["FILLED", "EXECUTED", "REJECTED", "CANCELLED", "CANCELED"]
    )
    assert filled_buy["status"] in [
        "FILLED",
        "EXECUTED",
    ], f"BUY order failed or cancelled: {filled_buy}"
    assert float(filled_buy["average_fill_price"]) > 0

    # 4. Check trades for this order
    trades_resp = requests.get(
        f"{API_GATEWAY_URL}/orders/{buy_id}/trades", headers=headers
    )
    assert trades_resp.status_code == 200
    trades = trades_resp.json()
    assert len(trades) >= 1
    assert trades[0]["order_id"] == buy_id
    assert float(trades[0]["quantity"]) == 0.5

    # 5. Check wallet balance updated (ETH should be >= 0.5)
    eth_bal = wait_for_balance(headers, "ETH", 0.5)
    assert float(eth_bal["available"]) >= 0.5

    # 6. Place SELL Market order for 0.5 ETH/USD
    sell_payload = {
        "symbol": "ETH/USD",
        "side": "SELL",
        "order_type": "MARKET",
        "quantity": 0.5,
    }
    resp_sell = requests.post(
        f"{API_GATEWAY_URL}/orders/", json=sell_payload, headers=headers
    )
    assert (
        resp_sell.status_code == 202
    ), f"Failed to place SELL market order: {resp_sell.text}"
    sell_order = resp_sell.json()
    sell_id = sell_order["id"]

    # 7. Poll SELL order status until FILLED
    filled_sell = wait_for_order_status(
        headers, sell_id, ["FILLED", "EXECUTED", "REJECTED", "CANCELLED", "CANCELED"]
    )
    assert filled_sell["status"] in [
        "FILLED",
        "EXECUTED",
    ], f"SELL order failed: {filled_sell}"

    # 8. Check user trade history contains both BUY and SELL trades
    history_resp = requests.get(
        f"{API_GATEWAY_URL}/orders/user/{user_id}/trades", headers=headers
    )
    assert history_resp.status_code == 200
    user_trades = history_resp.json()
    assert len(user_trades) >= 2
    order_ids_in_history = [t["order_id"] for t in user_trades]
    assert buy_id in order_ids_in_history
    assert sell_id in order_ids_in_history

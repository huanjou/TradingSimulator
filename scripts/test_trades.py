import time

import requests

API_URL = "http://localhost:8000/api/v1/orders"
USER_ID = "11111111-1111-1111-1111-111111111111"


def test():
    # 1. Create a market order
    payload = {
        "user_id": USER_ID,
        "symbol": "ETH/USD",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.5,
    }
    print("Creating order:", payload)
    resp = requests.post(API_URL, json=payload)
    print("Response:", resp.status_code, resp.text)

    if resp.status_code != 202:
        return

    order_data = resp.json()
    order_id = order_data["id"]

    # Wait for execution
    print(f"Waiting for order {order_id} to be executed...")
    time.sleep(2)

    # 2. Get order status
    resp = requests.get(f"{API_URL}/{order_id}")
    print("Order status:", resp.status_code, resp.text)

    # 3. Get trades
    resp = requests.get(f"{API_URL}/{order_id}/trades")
    print("Trades:", resp.status_code, resp.text)


if __name__ == "__main__":
    test()

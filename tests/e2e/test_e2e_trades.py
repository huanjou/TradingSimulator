import time

import pytest
import requests

API_GATEWAY_URL = "http://localhost:8000/api/v1"
USER_SERVICE_URL = "http://localhost:8003/api/v1"

ADMIN_EMAIL = "admin@admin.com"
ADMIN_PASSWORD = "admin"


@pytest.fixture(scope="session")
def auth_headers():
    """
    Authenticate as admin and return headers with JWT token.
    Requires user-service to be running and seeded.
    """
    login_url = f"{USER_SERVICE_URL}/auth/login"
    payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "remember_me": False}
    resp = requests.post(login_url, json=payload)
    assert resp.status_code == 200, f"Login failed: {resp.text}"

    data = resp.json()
    token = data["access_token"]
    user_id = data["user_id"]

    headers = {"Authorization": f"Bearer {token}"}
    return headers, user_id


def test_create_and_query_market_order(auth_headers):
    headers, user_id = auth_headers
    orders_url = f"{API_GATEWAY_URL}/orders"

    # 1. Create a market order
    payload = {
        "user_id": user_id,
        "symbol": "ETH/USD",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.5,
    }

    print("\nCreating order:", payload)
    resp = requests.post(orders_url, json=payload, headers=headers)
    assert resp.status_code == 202, f"Failed to create order: {resp.text}"

    order_data = resp.json()
    order_id = order_data["id"]
    assert order_id is not None

    # Wait for execution (engine runs asynchronously)
    print(f"Waiting for order {order_id} to be processed...")
    max_retries = 10
    processed = False

    for _ in range(max_retries):
        time.sleep(1)
        resp = requests.get(f"{orders_url}/{order_id}", headers=headers)
        assert resp.status_code == 200
        status_data = resp.json()
        print("Order status:", status_data["status"])

        # A market order without counterparty liquidity will be
        # REJECTED or CANCELLED, or FILLED/EXECUTED
        # if there is liquidity
        if status_data["status"] in ["EXECUTED", "FILLED", "REJECTED", "CANCELLED"]:
            processed = True
            break

    assert processed, "Order was not processed within timeout"

    # 3. Get trades
    resp = requests.get(f"{orders_url}/{order_id}/trades", headers=headers)
    assert resp.status_code == 200
    trades = resp.json()
    print("Trades:", trades)
    assert isinstance(trades, list)

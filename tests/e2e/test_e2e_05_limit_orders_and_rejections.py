import time

import requests
from conftest import (
    API_GATEWAY_URL,
    WALLET_SERVICE_URL,
    wait_for_balance,
    wait_for_order_status,
)


def test_limit_buy_below_market_stays_pending_and_locks_funds(new_user_factory):
    # 1. User deposits 5,000 USD
    user = new_user_factory(deposit_usd=5000.0)
    headers = user["headers"]

    # 2. Place LIMIT BUY for 1.0 ETH/USD at $500.00 (well below market ~1950)
    payload = {
        "symbol": "ETH/USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": 500.0,
        "quantity": 1.0,
    }
    resp = requests.post(f"{API_GATEWAY_URL}/orders/", json=payload, headers=headers)
    assert resp.status_code == 202, f"Failed to place limit BUY order: {resp.text}"
    order_id = resp.json()["id"]

    # 3. Wait a moment for Kafka processing, then verify order is PENDING
    time.sleep(1.5)
    order_resp = requests.get(f"{API_GATEWAY_URL}/orders/{order_id}", headers=headers)
    assert order_resp.status_code == 200
    order_data = order_resp.json()
    assert (
        order_data["status"] == "PENDING"
    ), f"Expected PENDING order, got {order_data['status']}"

    # 4. Check wallet: 500.0 USD should be locked, available should be 4500.0
    wallets_resp = requests.get(f"{WALLET_SERVICE_URL}/wallets/me", headers=headers)
    assert wallets_resp.status_code == 200
    usd_bal = next(b for b in wallets_resp.json()["balances"] if b["currency"] == "USD")
    assert (
        float(usd_bal["locked"]) >= 500.0
    ), f"Expected locked >= 500, got {usd_bal['locked']}"
    assert float(usd_bal["available"]) <= 4500.0


def test_limit_sell_above_market_stays_pending_and_locks_eth(new_user_factory):
    # 1. User deposits 5.0 ETH
    user = new_user_factory(deposit_eth=5.0)
    headers = user["headers"]

    # 2. Place LIMIT SELL for 2.0 ETH/USD at $15,000.00 (well above market ~1950)
    payload = {
        "symbol": "ETH/USD",
        "side": "SELL",
        "order_type": "LIMIT",
        "price": 15000.0,
        "quantity": 2.0,
    }
    resp = requests.post(f"{API_GATEWAY_URL}/orders/", json=payload, headers=headers)
    assert resp.status_code == 202
    order_id = resp.json()["id"]

    # 3. Verify order stays PENDING
    time.sleep(1.5)
    order_resp = requests.get(f"{API_GATEWAY_URL}/orders/{order_id}", headers=headers)
    assert order_resp.status_code == 200
    assert order_resp.json()["status"] == "PENDING"

    # 4. Check wallet: 2.0 ETH should be locked, available should be 3.0
    wallets_resp = requests.get(f"{WALLET_SERVICE_URL}/wallets/me", headers=headers)
    eth_bal = next(b for b in wallets_resp.json()["balances"] if b["currency"] == "ETH")
    assert float(eth_bal["locked"]) >= 2.0
    assert float(eth_bal["available"]) <= 3.0


def test_limit_buy_crossing_market_executes_immediately(new_user_factory):
    # 1. User deposits 10,000 USD
    user = new_user_factory(deposit_usd=10000.0)
    headers = user["headers"]

    # 2. Place LIMIT BUY for 0.5 ETH/USD at $5,000.00 (above market price ~1950)
    payload = {
        "symbol": "ETH/USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": 5000.0,
        "quantity": 0.5,
    }
    resp = requests.post(f"{API_GATEWAY_URL}/orders/", json=payload, headers=headers)
    assert resp.status_code == 202
    order_id = resp.json()["id"]

    # 3. Poll order until FILLED
    filled = wait_for_order_status(headers, order_id, ["FILLED", "EXECUTED"])
    # Verify average fill price <= limit price (should fill around market ~1950)
    assert float(filled["average_fill_price"]) <= 5000.0

    # 4. Verify user received 0.5 ETH
    eth_bal = wait_for_balance(headers, "ETH", 0.5)
    assert float(eth_bal["available"]) >= 0.5


def test_order_rejection_insufficient_funds(new_user_factory):
    # 1. Create user with NO deposits (0 balance)
    user = new_user_factory()
    headers = user["headers"]

    # 2. Place BUY order requiring funds
    payload = {
        "symbol": "BTC/USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": 50000.0,
        "quantity": 1.0,
    }
    resp = requests.post(f"{API_GATEWAY_URL}/orders/", json=payload, headers=headers)
    assert resp.status_code == 202
    order_id = resp.json()["id"]

    # 3. Poll order status: engine should reject it due to insufficient balance
    rejected = wait_for_order_status(
        headers, order_id, ["REJECTED", "CANCELLED", "CANCELED"]
    )
    assert rejected["status"] in [
        "REJECTED",
        "CANCELLED",
        "CANCELED",
    ], f"Expected rejection, got {rejected}"


def test_invalid_order_payload_validation(new_user_factory):
    user = new_user_factory()
    headers = user["headers"]

    # Limit order without price
    payload = {
        "symbol": "ETH/USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 1.0,
    }
    resp = requests.post(f"{API_GATEWAY_URL}/orders/", json=payload, headers=headers)
    assert (
        resp.status_code == 422
    ), f"Expected 422 for limit order without price, got {resp.status_code}"

import requests
from conftest import WALLET_SERVICE_URL, wait_for_balance


def test_initial_user_wallets_empty(new_user_factory):
    user = new_user_factory()
    headers = user["headers"]

    resp = requests.get(f"{WALLET_SERVICE_URL}/wallets/me", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch initial wallets: {resp.text}"
    data = resp.json()
    balances = data.get("balances", [])
    # Initially for a fresh user, balances might be empty or 0.0
    for b in balances:
        assert float(b["available"]) == 0.0
        assert float(b["locked"]) == 0.0


def test_deposit_multiple_currencies_and_polling(new_user_factory):
    user = new_user_factory()
    headers = user["headers"]

    # Deposit USD
    resp_usd = requests.post(
        f"{WALLET_SERVICE_URL}/wallets/deposit",
        json={"currency": "USD", "amount": 15000.50},
        headers=headers,
    )
    assert resp_usd.status_code == 202, f"USD deposit failed: {resp_usd.text}"
    data_usd = resp_usd.json()
    assert data_usd["status"] == "success"
    assert "command_id" in data_usd

    # Deposit ETH
    resp_eth = requests.post(
        f"{WALLET_SERVICE_URL}/wallets/deposit",
        json={"currency": "ETH", "amount": 10.0},
        headers=headers,
    )
    assert resp_eth.status_code == 202, f"ETH deposit failed: {resp_eth.text}"

    # Poll until both balances are updated via Kafka
    usd_bal = wait_for_balance(headers, "USD", 15000.50)
    eth_bal = wait_for_balance(headers, "ETH", 10.0)

    assert float(usd_bal["available"]) >= 15000.50
    assert float(eth_bal["available"]) >= 10.0


def test_deposit_invalid_amount(new_user_factory):
    user = new_user_factory()
    headers = user["headers"]

    # Negative amount
    resp_neg = requests.post(
        f"{WALLET_SERVICE_URL}/wallets/deposit",
        json={"currency": "USD", "amount": -100.0},
        headers=headers,
    )
    assert (
        resp_neg.status_code == 422
    ), f"Expected 422 for negative deposit, got {resp_neg.status_code}"

    # Zero amount
    resp_zero = requests.post(
        f"{WALLET_SERVICE_URL}/wallets/deposit",
        json={"currency": "USD", "amount": 0.0},
        headers=headers,
    )
    assert (
        resp_zero.status_code == 422
    ), f"Expected 422 for zero deposit, got {resp_zero.status_code}"


def test_deposit_unauthorized():
    resp = requests.post(
        f"{WALLET_SERVICE_URL}/wallets/deposit",
        json={"currency": "USD", "amount": 1000.0},
    )
    assert resp.status_code in [
        401,
        403,
    ], f"Expected 401/403 for missing auth, got {resp.status_code}"

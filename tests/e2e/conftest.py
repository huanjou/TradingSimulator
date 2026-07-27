import os
import time
import uuid

import pytest
import requests

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000/api/v1")
QUERY_SERVICE_URL = os.getenv("QUERY_SERVICE_URL", "http://localhost:8001/api/v1")
STREAM_SERVICE_URL = os.getenv("STREAM_SERVICE_URL", "http://localhost:8002/api/v1")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8003/api/v1")
WALLET_SERVICE_URL = os.getenv("WALLET_SERVICE_URL", "http://localhost:8005/api/v1")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@admin.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")


def wait_for_balance(
    headers: dict, currency: str, min_amount: float, timeout: int = 15
) -> dict:
    """
    Polls the wallet service until currency available balance is >= min_amount.
    Returns the matching balance dict.
    """
    start_time = time.time()
    url = f"{WALLET_SERVICE_URL}/wallets/me"
    while time.time() - start_time < timeout:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            balances = data.get("balances", [])
            for b in balances:
                if b["currency"] == currency:
                    avail = float(b["available"])
                    if avail >= min_amount:
                        return b
        time.sleep(0.5)
    raise TimeoutError(
        f"Balance for {currency} did not reach {min_amount} within {timeout}s."
    )


def wait_for_order_status(
    headers: dict, order_id: str, expected_statuses: list[str], timeout: int = 15
) -> dict:
    """
    Polls the order query endpoint until order status is in expected_statuses.
    Returns the order dict.
    """
    start_time = time.time()
    url = f"{API_GATEWAY_URL}/orders/{order_id}"
    last_status = None
    while time.time() - start_time < timeout:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            last_status = data.get("status")
            if last_status in expected_statuses:
                return data
        time.sleep(0.5)
    msg = (
        f"Order {order_id} did not reach {expected_statuses} within {timeout}s "
        f"(last: {last_status})."
    )
    raise TimeoutError(msg)


@pytest.fixture(scope="session")
def admin_headers():
    """
    Authenticate as admin and return (headers, user_id).
    """
    login_url = f"{USER_SERVICE_URL}/auth/login"
    payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "remember_me": False}
    resp = requests.post(login_url, json=payload)
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user_id"]


@pytest.fixture
def new_user_factory():
    """
    Factory fixture to create and login a clean test user.
    Optionally pre-deposits initial USD and ETH balances.
    """

    def _create_user(deposit_usd: float = 0.0, deposit_eth: float = 0.0):
        unique_id = uuid.uuid4().hex[:8]
        email = f"test_{unique_id}@e2e.com"
        password = "TestPassword123!"

        # Register
        reg_url = f"{USER_SERVICE_URL}/auth/register"
        reg_resp = requests.post(reg_url, json={"email": email, "password": password})
        assert (
            reg_resp.status_code == 201
        ), f"Failed to register user {email}: {reg_resp.text}"
        user_data = reg_resp.json()
        user_id = user_data["id"]

        # Login
        login_url = f"{USER_SERVICE_URL}/auth/login"
        login_resp = requests.post(
            login_url, json={"email": email, "password": password}
        )
        assert (
            login_resp.status_code == 200
        ), f"Failed to login user {email}: {login_resp.text}"
        login_data = login_resp.json()
        headers = {"Authorization": f"Bearer {login_data['access_token']}"}

        # Deposit initial balances if specified
        if deposit_usd > 0:
            dep_resp = requests.post(
                f"{WALLET_SERVICE_URL}/wallets/deposit",
                json={"currency": "USD", "amount": deposit_usd},
                headers=headers,
            )
            assert (
                dep_resp.status_code == 202
            ), f"Failed to deposit USD: {dep_resp.text}"
            wait_for_balance(headers, "USD", deposit_usd)

        if deposit_eth > 0:
            dep_resp = requests.post(
                f"{WALLET_SERVICE_URL}/wallets/deposit",
                json={"currency": "ETH", "amount": deposit_eth},
                headers=headers,
            )
            assert (
                dep_resp.status_code == 202
            ), f"Failed to deposit ETH: {dep_resp.text}"
            wait_for_balance(headers, "ETH", deposit_eth)

        return {
            "email": email,
            "password": password,
            "user_id": user_id,
            "headers": headers,
            "access_token": login_data["access_token"],
        }

    return _create_user

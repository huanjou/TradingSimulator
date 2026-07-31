import requests
from conftest import API_GATEWAY_URL, QUERY_SERVICE_URL


def test_get_symbols_default_list():
    resp = requests.get(f"{QUERY_SERVICE_URL}/symbols")
    assert resp.status_code == 200, f"Failed to get symbols: {resp.text}"
    symbols = resp.json()
    assert isinstance(symbols, list)
    assert len(symbols) >= 10

    import json
    import os

    symbols_path = os.path.join(
        os.path.dirname(__file__), "../../config/seed/symbols.json"
    )
    with open(symbols_path, "r") as f:
        expected_symbols = json.load(f)

    for expected in expected_symbols:
        assert any(
            item["name"] == expected for item in symbols
        ), f"{expected} missing from symbols list"

    for s in symbols:
        assert s["is_active"] is True


def test_filter_symbols():
    resp = requests.get(f"{QUERY_SERVICE_URL}/symbols", params={"q": "ETH"})
    assert resp.status_code == 200
    symbols = resp.json()
    assert len(symbols) >= 1
    for s in symbols:
        assert "ETH" in s["name"].upper()


def test_admin_create_symbol(admin_headers):
    headers, admin_id = admin_headers
    new_symbol = "LTC/USD"

    resp = requests.post(
        f"{API_GATEWAY_URL}/admin/symbols",
        json={"symbol": new_symbol},
        headers=headers,
    )
    assert resp.status_code == 202, f"Admin create symbol failed: {resp.text}"
    data = resp.json()
    assert data["status"] == "success"


def test_non_admin_create_symbol_forbidden(new_user_factory):
    user = new_user_factory()
    headers = user["headers"]

    resp = requests.post(
        f"{API_GATEWAY_URL}/admin/symbols",
        json={"symbol": "XRP/USD"},
        headers=headers,
    )
    assert resp.status_code in [
        401,
        403,
    ], f"Expected 401/403 for non-admin symbol creation, got {resp.status_code}"

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_symbol_success(admin_client):
    """Happy Path: Test creating a symbol with admin auth."""
    client, user = admin_client
    payload = {"symbol": "TSLA/USD"}

    with patch(
        "app.services.admin.AdminService.create_symbol", return_value="evt-123"
    ) as mock_create:
        response = await client.post("/api/v1/admin/symbols", json=payload)

        # We expect a 202 accepted
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "success"

        # Verify service was called
        mock_create.assert_called_once_with("TSLA/USD")


@pytest.mark.asyncio
async def test_create_symbol_forbidden(auth_client):
    """Sad Path: Test creating a symbol with normal user auth."""
    client, user = auth_client
    payload = {"symbol": "AAPL/USD"}

    response = await client.post("/api/v1/admin/symbols", json=payload)

    # 403 Forbidden because role is not admin
    assert response.status_code == 403
    assert "Not enough permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_symbol_unauthorized(client: AsyncClient):
    """Sad Path: Test creating a symbol without any auth."""
    payload = {"symbol": "GOOGL/USD"}

    response = await client.post("/api/v1/admin/symbols", json=payload)

    # 401 Unauthorized because no token
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]

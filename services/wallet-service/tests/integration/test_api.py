import pytest
from app.api.deps import get_current_user_id
from app.main import app
from httpx import AsyncClient


# Mock dependencies
async def override_get_current_user_id():
    return "user1"


app.dependency_overrides[get_current_user_id] = override_get_current_user_id


@pytest.mark.asyncio
async def test_get_my_wallets(mocker):
    mock_get_wallets = mocker.patch(
        "app.api.endpoints.wallets.wallet_repo.get_wallets_by_user"
    )

    from app.schemas.wallet import Wallet

    mock_get_wallets.return_value = {
        "USD": Wallet(currency="USD", available=100.0, locked=0.0)
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/wallets/me")

    assert response.status_code == 200
    data = response.json()
    assert "USD" in data
    assert data["USD"]["available"] == 100.0


@pytest.mark.asyncio
async def test_deposit(mocker):
    mock_deposit = mocker.patch("app.api.endpoints.wallets.wallet_service.deposit")

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/wallets/deposit", json={"currency": "USD", "amount": 500.0}
        )

    assert response.status_code == 202
    mock_deposit.assert_called_once_with("user1", "USD", 500.0)

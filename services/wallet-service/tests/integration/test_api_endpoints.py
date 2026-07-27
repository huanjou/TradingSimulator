from unittest.mock import AsyncMock, patch

import pytest
from app.api.deps import get_current_user_id
from app.core.redis import get_redis
from app.main import app
from httpx import AsyncClient


@pytest.fixture
def client_with_auth(fake_redis):
    async def override_user():
        return "user_int"

    async def override_redis():
        yield fake_redis

    app.dependency_overrides[get_current_user_id] = override_user
    app.dependency_overrides[get_redis] = override_redis
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_wallets_integration(client_with_auth, fake_redis):
    # Предзаполняем Redis реальными данными
    fake_redis.storage["wallet:user_int"] = {
        "USD": '{"currency": "USD", "available": "5000.00", "locked": "100.00"}',
        "BTC": '{"currency": "BTC", "available": "2.50", "locked": "0.10"}',
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/wallets/me")

    assert response.status_code == 200
    data = response.json()
    assert len(data["balances"]) == 2
    currencies = {b["currency"]: b for b in data["balances"]}
    assert currencies["USD"]["available"] == "5000.00"
    assert currencies["BTC"]["locked"] == "0.10"


@pytest.mark.asyncio
@patch("app.services.wallet_service.kafka_client")
async def test_deposit_integration_valid(mock_kafka, client_with_auth):
    mock_kafka.send_command = AsyncMock()

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/wallets/deposit", json={"currency": "btc ", "amount": 1.5}
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "success"
    assert "command_id" in data

    mock_kafka.send_command.assert_called_once()
    kwargs = mock_kafka.send_command.call_args.kwargs
    assert kwargs["value"]["currency"] == "BTC"
    assert kwargs["value"]["amount"] == "1.5"


@pytest.mark.asyncio
async def test_deposit_integration_validation_error_negative_amount(client_with_auth):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/wallets/deposit", json={"currency": "USD", "amount": -100}
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_deposit_integration_validation_error_zero_amount(client_with_auth):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/wallets/deposit", json={"currency": "USD", "amount": 0}
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_deposit_integration_validation_error_empty_currency(client_with_auth):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/wallets/deposit", json={"currency": "", "amount": 100}
        )
    assert response.status_code == 422

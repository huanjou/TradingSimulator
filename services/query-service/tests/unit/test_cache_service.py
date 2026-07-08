from unittest.mock import AsyncMock

import pytest

from app.services.cache_service import get_cached_order


@pytest.mark.asyncio
async def test_get_cached_order_hit(monkeypatch):
    mock_redis = AsyncMock()

    order_data = {
        "id": "c5b24888-297c-4ab4-80cf-f273ed952b65",
        "symbol": "AAPL",
        "status": "PENDING",
    }

    mock_redis.hgetall.return_value = order_data

    monkeypatch.setattr("app.services.cache_service.redis_client", mock_redis)

    result = await get_cached_order("c5b24888-297c-4ab4-80cf-f273ed952b65")

    assert result == order_data
    mock_redis.hgetall.assert_called_once_with(
        "order:c5b24888-297c-4ab4-80cf-f273ed952b65"
    )


@pytest.mark.asyncio
async def test_get_cached_order_miss(monkeypatch):
    mock_redis = AsyncMock()

    mock_redis.hgetall.return_value = {}

    monkeypatch.setattr("app.services.cache_service.redis_client", mock_redis)

    result = await get_cached_order("c5b24888-297c-4ab4-80cf-f273ed952b65")

    assert result is None
    mock_redis.hgetall.assert_called_once_with(
        "order:c5b24888-297c-4ab4-80cf-f273ed952b65"
    )


@pytest.mark.asyncio
async def test_get_cached_order_invalid_json(monkeypatch):
    mock_redis = AsyncMock()

    mock_redis.hgetall.side_effect = Exception("Redis error")

    monkeypatch.setattr("app.services.cache_service.redis_client", mock_redis)

    result = await get_cached_order("c5b24888-297c-4ab4-80cf-f273ed952b65")

    assert result is None

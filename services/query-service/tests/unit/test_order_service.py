from unittest.mock import AsyncMock, MagicMock

import pytest
from app.domain.order import OrderEntity
from app.services.order_service import get_order_by_id


@pytest.mark.asyncio
async def test_get_order_by_id_cache_hit(monkeypatch):
    mock_repo = AsyncMock()

    mock_order_dict = {
        "id": "c5b24888-297c-4ab4-80cf-f273ed952b65",
        "user_id": "user1",
        "symbol": "AAPL",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 10.0,
        "price": 150.0,
        "status": "FILLED",
    }

    async def mock_get_cached(*args, **kwargs):
        return mock_order_dict

    monkeypatch.setattr("app.services.order_service.get_cached_order", mock_get_cached)

    # Mock metrics
    mock_hits_counter = MagicMock()
    monkeypatch.setattr(
        "app.services.order_service.cache_hits_counter.add", mock_hits_counter
    )

    order = await get_order_by_id(mock_repo, "c5b24888-297c-4ab4-80cf-f273ed952b65")

    assert order is not None
    assert order.id == "c5b24888-297c-4ab4-80cf-f273ed952b65"
    assert order.symbol == "AAPL"

    # DB shouldn't be called
    mock_repo.get_by_id.assert_not_called()
    mock_hits_counter.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_get_order_by_id_cache_miss(monkeypatch):
    mock_repo = AsyncMock()

    async def mock_get_cached(*args, **kwargs):
        return None

    async def mock_set_cached(*args, **kwargs):
        pass

    monkeypatch.setattr("app.services.order_service.get_cached_order", mock_get_cached)
    monkeypatch.setattr("app.services.order_service.set_cached_order", mock_set_cached)

    # Mock metrics
    mock_misses_counter = MagicMock()
    monkeypatch.setattr(
        "app.services.order_service.cache_misses_counter.add", mock_misses_counter
    )

    mock_order = OrderEntity(
        id="c5b24888-297c-4ab4-80cf-f273ed952b65",
        user_id="user1",
        symbol="AAPL",
        side="BUY",
        order_type="LIMIT",
        quantity=10.0,
        price=150.0,
        status="FILLED",
    )
    mock_repo.get_by_id.return_value = mock_order

    order = await get_order_by_id(mock_repo, "c5b24888-297c-4ab4-80cf-f273ed952b65")

    assert order is not None
    assert order.id == "c5b24888-297c-4ab4-80cf-f273ed952b65"

    mock_repo.get_by_id.assert_called_once_with("c5b24888-297c-4ab4-80cf-f273ed952b65")
    mock_misses_counter.assert_called_once_with(1)

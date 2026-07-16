from unittest.mock import AsyncMock

import pytest
from app.domain.order import OrderEntity
from app.services.order_service import get_order_by_id


@pytest.mark.asyncio
async def test_get_order_by_id_cache_hit(monkeypatch):
    mock_db = AsyncMock()

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

    order = await get_order_by_id(mock_db, "c5b24888-297c-4ab4-80cf-f273ed952b65")

    assert order is not None
    assert order.id == "c5b24888-297c-4ab4-80cf-f273ed952b65"
    assert order.symbol == "AAPL"

    # DB shouldn't be called
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_order_by_id_cache_miss(monkeypatch):
    mock_db = AsyncMock()

    async def mock_get_cached(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.order_service.get_cached_order", mock_get_cached)

    mock_repo_instance = AsyncMock()
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
    mock_repo_instance.get_by_id.return_value = mock_order

    monkeypatch.setattr(
        "app.services.order_service.OrderRepository", lambda db: mock_repo_instance
    )

    order = await get_order_by_id(mock_db, "c5b24888-297c-4ab4-80cf-f273ed952b65")

    assert order is not None
    assert order.id == "c5b24888-297c-4ab4-80cf-f273ed952b65"

    mock_repo_instance.get_by_id.assert_called_once_with(
        "c5b24888-297c-4ab4-80cf-f273ed952b65"
    )

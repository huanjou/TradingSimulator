import json
from decimal import Decimal

import fakeredis.aioredis
import pytest
from app.domain.engine import MatchingEngine
from app.domain.order import Order, OrderSide, OrderType
from app.services.snapshot_service import SnapshotManager


@pytest.fixture
def redis_client():
    # Provide a fake asynchronous Redis client
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def snapshot_manager(redis_client):
    return SnapshotManager(redis_client)


@pytest.fixture
def engine():
    return MatchingEngine()


@pytest.mark.asyncio
async def test_save_snapshot(snapshot_manager, engine, redis_client):
    # Setup some pending orders
    order = Order(
        id="test1",
        user_id="u1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("50000"),
        quantity=Decimal("1.5"),
    )
    engine.process_order(order)

    offsets = {"orders": {"0": 12345}}

    # Act
    await snapshot_manager.save_snapshot(engine, offsets)

    # Assert
    raw_data = await redis_client.get(snapshot_manager.snapshot_key)
    assert raw_data is not None

    data = json.loads(raw_data)
    assert data["offsets"] == {"orders": {"0": 12345}}
    assert len(data["pending_orders"]) == 1
    assert data["pending_orders"][0]["id"] == "test1"


@pytest.mark.asyncio
async def test_load_latest_snapshot(snapshot_manager, engine, redis_client):
    # Setup state in redis directly
    offsets = {"orders": {"0": 999}}
    order_data = {
        "id": "test2",
        "user_id": "u2",
        "symbol": "ETHUSDT",
        "side": "SELL",
        "order_type": "LIMIT",
        "price": "3000.0",
        "quantity": "10.0",
    }

    snapshot_data = {"offsets": offsets, "pending_orders": [order_data]}

    await redis_client.set(snapshot_manager.snapshot_key, json.dumps(snapshot_data))

    # Act
    orders, loaded_offsets = await snapshot_manager.load_latest_snapshot()

    # Assert
    assert loaded_offsets == offsets
    assert len(orders) == 1
    assert orders[0].id == "test2"
    assert orders[0].symbol == "ETHUSDT"
    assert orders[0].price == Decimal("3000.0")


@pytest.mark.asyncio
async def test_load_empty_snapshot(snapshot_manager, redis_client):
    # Ensure redis is empty
    await redis_client.flushall()

    # Act
    orders, loaded_offsets = await snapshot_manager.load_latest_snapshot()

    # Assert
    assert len(orders) == 0
    assert loaded_offsets == {}

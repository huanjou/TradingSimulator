import json
from decimal import Decimal

import fakeredis.aioredis
import pytest
from app.domain.engine import MatchingEngine, WalletInfo
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
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("50000"),
        quantity=Decimal("1.5"),
    )
    # Setup some wallets
    engine.wallets["u1"] = {
        "BTC": WalletInfo(available=Decimal("1.0"), locked=Decimal("0.5")),
        "USDT": WalletInfo(available=Decimal("100000.0"), locked=Decimal("0")),
    }
    engine.user_balance_versions["u1"] = 2

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
    assert data["wallets"]["u1"]["BTC"]["available"] == "1.0"
    assert data["wallets"]["u1"]["BTC"]["locked"] == "0.5"
    assert data["balance_versions"] == {"u1": 2}


@pytest.mark.asyncio
async def test_load_latest_snapshot(snapshot_manager, engine, redis_client):
    # Setup state in redis directly
    offsets = {"orders": {"0": 999}}
    order_data = {
        "id": "test2",
        "user_id": "u2",
        "symbol": "ETH/USDT",
        "side": "SELL",
        "order_type": "LIMIT",
        "price": "3000.0",
        "quantity": "10.0",
    }

    wallet_data = {"u2": {"ETH": {"available": "5.0", "locked": "10.0"}}}

    snapshot_data = {
        "offsets": offsets,
        "pending_orders": [order_data],
        "wallets": wallet_data,
        "balance_versions": {"u2": 3},
    }

    await redis_client.set(snapshot_manager.snapshot_key, json.dumps(snapshot_data))

    # Act
    (
        orders,
        loaded_offsets,
        wallets,
        balance_versions,
    ) = await snapshot_manager.load_latest_snapshot()

    # Assert
    assert loaded_offsets == offsets
    assert len(orders) == 1
    assert orders[0].id == "test2"
    assert orders[0].symbol == "ETH/USDT"
    assert orders[0].price == Decimal("3000.0")

    assert wallets["u2"]["ETH"]["available"] == "5.0"
    assert wallets["u2"]["ETH"]["locked"] == "10.0"

    assert balance_versions == {"u2": 3}


@pytest.mark.asyncio
async def test_load_empty_snapshot(snapshot_manager, redis_client):
    # Ensure redis is empty
    await redis_client.flushall()

    # Act
    (
        orders,
        loaded_offsets,
        wallets,
        balance_versions,
    ) = await snapshot_manager.load_latest_snapshot()

    # Assert
    assert len(orders) == 0
    assert loaded_offsets == {}
    assert wallets == {}
    assert balance_versions == {}

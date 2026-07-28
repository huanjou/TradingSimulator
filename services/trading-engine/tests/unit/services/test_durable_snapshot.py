from decimal import Decimal

import orjson
import pytest
from app.services import durable_snapshot
from app.services.durable_snapshot import DurableSnapshotStore


class _FakeConn:
    def __init__(self, store):
        self._store = store

    async def execute(self, query, *args):
        self._store["executes"].append((query, args))

    async def fetchrow(self, query, *args):
        return self._store.get("row")


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, store):
        self._store = store
        self._conn = _FakeConn(store)

    def acquire(self):
        return _FakeAcquire(self._conn)

    async def close(self):
        self._store["closed"] = True


@pytest.fixture
def fake_pool(monkeypatch):
    store = {"executes": [], "row": None, "closed": False}

    async def _create_pool(dsn, **kwargs):
        store["dsn"] = dsn
        return _FakePool(store)

    monkeypatch.setattr(durable_snapshot.asyncpg, "create_pool", _create_pool)
    return store


@pytest.mark.asyncio
async def test_connect_strips_driver_and_ensure_schema(fake_pool):
    s = DurableSnapshotStore("postgresql+asyncpg://u:p@host:5432/db")
    await s.connect()
    # DSN is normalized for asyncpg.
    assert fake_pool["dsn"] == "postgresql://u:p@host:5432/db"

    await s.ensure_schema()
    assert any("CREATE TABLE" in q for q, _ in fake_pool["executes"])


@pytest.mark.asyncio
async def test_save_upserts_full_snapshot(fake_pool):
    s = DurableSnapshotStore("postgresql://u:p@host:5432/db")
    await s.connect()

    snapshot = {
        "offsets": {"orders": {"0": 41}},
        "pending_orders": [],
        "wallets": {"u1": {"USD": {"available": "100", "locked": "0"}}},
    }
    await s.save(snapshot)

    upserts = [(q, a) for q, a in fake_pool["executes"] if "INSERT INTO" in q]
    assert len(upserts) == 1
    # The full snapshot is serialized as the single payload argument.
    payload = orjson.loads(upserts[0][1][0])
    assert payload == snapshot


@pytest.mark.asyncio
async def test_load_returns_exact_offsets_and_state(fake_pool):
    snapshot = {
        "offsets": {"orders": {"0": 41}, "wallet_commands": {"0": 40}},
        "pending_orders": [
            {
                "id": "order-1",
                "user_id": "user-1",
                "symbol": "BTC/USD",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": "1.0",
                "filled_quantity": "0",
                "price": "50000",
                "average_fill_price": None,
                "status": "PENDING",
            }
        ],
        "wallets": {"user-1": {"USD": {"available": "100.50", "locked": "10.00"}}},
        "balance_versions": {"user-1": 4},
    }
    # asyncpg returns jsonb as a str by default.
    fake_pool["row"] = {"data": orjson.dumps(snapshot).decode()}

    s = DurableSnapshotStore("postgresql://u:p@host:5432/db")
    await s.connect()
    orders, offsets, wallets, balance_versions = await s.load()

    # Exact offsets are preserved for a precise (non seek_to_end) resume.
    assert offsets == {"orders": {"0": 41}, "wallet_commands": {"0": 40}}
    assert wallets["user-1"]["USD"] == {"available": "100.50", "locked": "10.00"}
    assert balance_versions == {"user-1": 4}
    assert len(orders) == 1
    assert orders[0].id == "order-1"
    assert orders[0].price == Decimal("50000")


@pytest.mark.asyncio
async def test_load_returns_empty_when_no_row(fake_pool):
    fake_pool["row"] = None
    s = DurableSnapshotStore("postgresql://u:p@host:5432/db")
    await s.connect()
    orders, offsets, wallets, balance_versions = await s.load()
    assert orders == []
    assert offsets == {}
    assert wallets == {}
    assert balance_versions == {}

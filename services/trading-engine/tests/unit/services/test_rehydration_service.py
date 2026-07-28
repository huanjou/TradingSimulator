from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from app.services import rehydration_service
from app.services.rehydration_service import _normalize_dsn, load_state_from_db


def test_normalize_dsn_strips_sqlalchemy_driver():
    assert (
        _normalize_dsn("postgresql+asyncpg://u:p@host:5432/db")
        == "postgresql://u:p@host:5432/db"
    )
    # Plain DSNs are left untouched.
    assert (
        _normalize_dsn("postgresql://u:p@host:5432/db")
        == "postgresql://u:p@host:5432/db"
    )


class _FakeConn:
    def __init__(self, balances, orders):
        self._balances = balances
        self._orders = orders
        self.closed = False

    async def fetch(self, query, *args):
        if "FROM balances" in query:
            return self._balances
        return self._orders

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_load_state_from_db_maps_rows(monkeypatch):
    balances = [
        {
            "user_id": "user-1",
            "currency": "USD",
            "available": Decimal("100.50"),
            "locked": Decimal("10.00"),
        },
        {
            "user_id": "user-1",
            "currency": "BTC",
            "available": Decimal("0.5"),
            "locked": Decimal("0"),
        },
    ]
    orders = [
        {
            "id": "order-1",
            "user_id": "user-1",
            "symbol": "BTC/USD",
            "side": "BUY",
            "order_type": "LIMIT",
            "quantity": Decimal("1.0"),
            "filled_quantity": Decimal("0"),
            "price": Decimal("50000"),
            "average_fill_price": None,
            "status": "PENDING",
        },
        # A row without a price must be skipped, not crash recovery.
        {
            "id": "order-2",
            "user_id": "user-1",
            "symbol": "BTC/USD",
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": Decimal("1.0"),
            "filled_quantity": Decimal("0"),
            "price": None,
            "average_fill_price": None,
            "status": "PENDING",
        },
    ]
    fake_conn = _FakeConn(balances, orders)
    monkeypatch.setattr(
        rehydration_service.asyncpg, "connect", AsyncMock(return_value=fake_conn)
    )

    wallets, open_orders = await load_state_from_db(
        "postgresql+asyncpg://u:p@host:5432/db"
    )

    # Wallets are grouped by user -> currency, values are strings.
    assert wallets["user-1"]["USD"] == {"available": "100.50", "locked": "10.00"}
    assert wallets["user-1"]["BTC"]["available"] == "0.5"

    # Only the priced LIMIT order is restored.
    assert len(open_orders) == 1
    assert open_orders[0].id == "order-1"
    assert open_orders[0].price == Decimal("50000")

    # Connection is always closed.
    assert fake_conn.closed is True

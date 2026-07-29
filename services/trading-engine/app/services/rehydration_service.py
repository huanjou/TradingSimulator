from decimal import Decimal
from typing import Dict, List, Tuple

import asyncpg
import structlog
from app.domain.order import Order

logger = structlog.get_logger(__name__)


def _normalize_dsn(url: str) -> str:
    """Strip the SQLAlchemy driver suffix so asyncpg can consume the DSN.

    The rest of the stack uses ``postgresql+asyncpg://...`` (SQLAlchemy style),
    but ``asyncpg.connect`` expects a plain ``postgresql://...`` DSN.
    """
    prefix = "postgresql+asyncpg://"
    if url.startswith(prefix):
        return "postgresql://" + url[len(prefix) :]
    return url


async def load_state_from_db(
    postgres_url: str,
) -> Tuple[Dict[str, Dict[str, dict]], List[Order]]:
    """Cold-start recovery source of truth.

    When no Redis snapshot exists (the snapshot store was wiped, or this is a
    fresh engine deployment against an existing ledger), the in-memory state
    must NOT start from zero. Otherwise the next absolute ``balance_update``
    the engine emits would overwrite the real balances in Postgres/Redis with
    ``0 + delta`` and destroy user funds.

    This reads the durable ledger (balances + open orders) directly from
    Postgres so the engine is rehydrated with the true state before it starts
    consuming.

    Returns ``(wallets_data, open_orders)`` in the shapes expected by
    ``MatchingEngine.restore_wallets`` / ``restore_orders``.
    """
    dsn = _normalize_dsn(postgres_url)
    conn = await asyncpg.connect(dsn)
    try:
        balance_rows = await conn.fetch(
            "SELECT user_id, currency, available, locked FROM balances"
        )
        order_rows = await conn.fetch(
            """
            SELECT id, user_id, symbol, side, order_type,
                   quantity, filled_quantity, price, average_fill_price, status
            FROM orders
            WHERE status IN ('PENDING', 'PARTIALLY_FILLED')
            """
        )
    except asyncpg.UndefinedTableError:
        # The ledger schema is owned by ledger-writer's migrations, which may
        # not have run yet on a brand new deployment (both services start as
        # soon as Postgres is healthy). A missing table means the ledger has
        # never held state, so starting empty cannot destroy any funds --
        # unlike crashing here, which would leave the engine in a restart loop.
        logger.warning("cold_start_ledger_schema_absent_starting_empty")
        return {}, []
    finally:
        await conn.close()

    wallets_data: Dict[str, Dict[str, dict]] = {}
    for row in balance_rows:
        user_id = str(row["user_id"])
        currency = row["currency"]
        wallets_data.setdefault(user_id, {})[currency] = {
            "available": str(row["available"]),
            "locked": str(row["locked"]),
        }

    orders: List[Order] = []
    for row in order_rows:
        # Only LIMIT orders ever rest on the book; guard against a stray row
        # without a price so recovery can't crash on it.
        if row["price"] is None:
            continue
        orders.append(
            Order(
                id=str(row["id"]),
                user_id=str(row["user_id"]),
                symbol=row["symbol"],
                side=row["side"],
                order_type=row["order_type"],
                quantity=Decimal(str(row["quantity"])),
                filled_quantity=Decimal(str(row["filled_quantity"] or "0")),
                price=Decimal(str(row["price"])),
                average_fill_price=(
                    Decimal(str(row["average_fill_price"]))
                    if row["average_fill_price"] is not None
                    else None
                ),
                status=row["status"],
            )
        )

    logger.info(
        "cold_start_rehydrated_from_db",
        wallets=len(wallets_data),
        open_orders=len(orders),
    )
    return wallets_data, orders

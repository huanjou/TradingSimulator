from typing import Dict, List, Optional, Tuple

import asyncpg
import orjson
import structlog
from app.domain.order import Order
from app.services.rehydration_service import _normalize_dsn

logger = structlog.get_logger(__name__)

# The engine owns this recovery table end-to-end (single writer), so it is
# created lazily with CREATE TABLE IF NOT EXISTS instead of an Alembic
# migration. This keeps the engine's boot independent of ledger-writer's
# migration ordering while remaining idempotent and safe.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS engine_snapshots (
    id INTEGER PRIMARY KEY,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT engine_snapshots_singleton CHECK (id = 1)
);
"""

_UPSERT = """
INSERT INTO engine_snapshots (id, data, updated_at)
VALUES (1, $1::jsonb, now())
ON CONFLICT (id) DO UPDATE
SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at;
"""


class DurableSnapshotStore:
    """Durable, point-in-time copy of the engine snapshot in Postgres.

    The Redis snapshot is fast but volatile: if it is lost, cold-start recovery
    can only rebuild *approximate* state from the CQRS ledger and resume from the
    Kafka HEAD (seek_to_end), which may drop in-flight wallet commands / orders
    that Postgres has not caught up on yet.

    Persisting the SAME atomic snapshot (wallets + pending_orders + Kafka
    offsets) here lets a cold-started engine resume from the EXACT offsets that
    produced the stored state, closing that loss window. Because offsets and
    state are written together (identical ``snapshot_data`` object), replaying
    from these offsets can never double-apply or skip.
    """

    def __init__(self, postgres_url: str):
        self._dsn = _normalize_dsn(postgres_url)
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=2)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def ensure_schema(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA)

    async def save(self, snapshot_data: dict) -> None:
        payload = orjson.dumps(snapshot_data).decode()
        async with self._pool.acquire() as conn:
            await conn.execute(_UPSERT, payload)

    async def load(
        self,
    ) -> Tuple[List[Order], Dict[str, Dict[str, int]], Dict[str, Dict[str, dict]]]:
        """Load the durable snapshot.

        Returns ``([], {}, {})`` when no durable snapshot exists yet (e.g. the
        very first boot after enabling this feature), so callers can fall
        through to the next recovery tier.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT data FROM engine_snapshots WHERE id = 1")

        if row is None or row["data"] is None:
            logger.info("no_durable_snapshot_in_postgres")
            return [], {}, {}

        raw = row["data"]
        # asyncpg returns jsonb as a str by default; be lenient either way.
        snapshot_data = orjson.loads(raw) if isinstance(raw, (str, bytes)) else raw
        offsets = snapshot_data.get("offsets", {})
        orders_data = snapshot_data.get("pending_orders", [])
        wallets_data = snapshot_data.get("wallets", {})

        orders = [Order.model_validate(data) for data in orders_data]
        logger.info(
            "durable_snapshot_loaded",
            orders_count=len(orders),
            offsets=offsets,
        )
        return orders, offsets, wallets_data

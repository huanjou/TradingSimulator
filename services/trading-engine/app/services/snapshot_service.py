import asyncio
import time
from typing import Dict, List, Tuple

import orjson
import redis.exceptions
import structlog
from app.domain.engine import MatchingEngine
from app.domain.order import Order
from redis.asyncio import Redis
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

# Errors indicating Redis is unreachable (as opposed to a bad command/data).
REDIS_ERRORS = (
    redis.exceptions.ConnectionError,
    redis.exceptions.TimeoutError,
    OSError,
)


def _log_redis_retry(retry_state):
    logger.warning(
        "redis_snapshot_retrying",
        attempt=retry_state.attempt_number,
        error=str(retry_state.outcome.exception()),
    )


async def periodic_snapshot_task(
    snapshot_manager: "SnapshotManager", engine: MatchingEngine, consumer
):
    """Periodically saves the trading engine state and Kafka offsets to Redis."""
    while True:
        await asyncio.sleep(10)  # Configurable interval
        try:
            await snapshot_manager.save_snapshot(engine, consumer.current_offsets)
        except Exception as e:
            logger.error("periodic_snapshot_failed", error=str(e))


class SnapshotManager:
    # While the circuit is open (Redis marked unavailable), only probe for a
    # reconnect once per this interval instead of retrying on every cycle.
    REDIS_RETRY_INTERVAL = 30.0

    def __init__(self, redis_client: Redis, durable_store=None):
        self.redis = redis_client
        # Optional durable (Postgres) mirror of the snapshot. When present, the
        # exact (wallets, pending_orders, offsets) triple is persisted there too,
        # so a cold start with a lost Redis snapshot can resume from the precise
        # offsets instead of guessing with seek_to_end.
        self.durable_store = durable_store
        self.snapshot_key = "trading_engine:snapshot"
        # Circuit breaker state for the Redis snapshot target.
        self._redis_available = True
        self._last_redis_attempt = 0.0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(REDIS_ERRORS),
        before_sleep=_log_redis_retry,
        reraise=True,
    )
    async def _redis_set_with_retry(self, key: str, data: bytes) -> None:
        await self.redis.set(key, data)

    async def _try_redis_snapshot(self, data: bytes) -> bool:
        """
        Write the snapshot to Redis behind a circuit breaker.
        While Redis is marked unavailable, only one reconnect attempt is made
        every REDIS_RETRY_INTERVAL seconds so a dead Redis never blocks the
        snapshot cycle. Returns True if the write succeeded.
        """
        now = time.monotonic()
        if (
            not self._redis_available
            and now - self._last_redis_attempt < self.REDIS_RETRY_INTERVAL
        ):
            # Circuit open: skip Redis until the next probe window.
            return False

        self._last_redis_attempt = now
        try:
            await self._redis_set_with_retry(self.snapshot_key, data)
        except REDIS_ERRORS as e:
            if self._redis_available:
                logger.critical(
                    "redis_snapshot_unavailable",
                    error=str(e),
                    retry_interval_seconds=self.REDIS_RETRY_INTERVAL,
                    exc_info=True,
                )
            else:
                logger.error("redis_snapshot_still_unavailable", error=str(e))
            self._redis_available = False
            return False

        if not self._redis_available:
            logger.info("redis_snapshot_recovered")
            self._redis_available = True
        return True

    async def save_snapshot(
        self, engine: MatchingEngine, offsets: Dict[str, Dict[str, int]]
    ) -> None:
        """
        Saves a snapshot of the engine's pending orders and the latest processed
        Kafka offsets.
        Offsets format expected: {topic: {partition: offset}}
        """
        try:
            # Flatten pending orders
            all_orders = [
                order.model_dump(mode="json")
                for order in engine.get_all_pending_orders()
            ]

            wallets_data = {}
            for user_id, user_wallets in engine.wallets.items():
                wallets_data[user_id] = {}
                for currency, wallet_info in user_wallets.items():
                    wallets_data[user_id][currency] = {
                        "available": str(wallet_info.available),
                        "locked": str(wallet_info.locked),
                    }

            snapshot_data = {
                # Deep-copy offsets so the persisted snapshot is a consistent
                # point-in-time pair of (wallets, pending_orders, offsets).
                # The whole block below runs without an await until redis.set,
                # so no consumer batch can interleave and desync state vs.
                # offsets -> replaying from these offsets can never double-apply.
                "offsets": {t: dict(parts) for t, parts in offsets.items()},
                "pending_orders": all_orders,
                "wallets": wallets_data,
                # Per-user balance versions so causal ordering of deposits vs.
                # orders (depends_on_balance_version) survives restarts.
                "balance_versions": dict(engine.user_balance_versions),
            }

            serialized = orjson.dumps(snapshot_data)
        except Exception as e:
            logger.error("failed_to_build_snapshot", error=str(e), exc_info=True)
            return

        # Best-effort Redis write behind the circuit breaker: a dead Redis must
        # never block the snapshot cycle, and the durable Postgres mirror below
        # keeps the state safe until Redis comes back.
        if await self._try_redis_snapshot(serialized):
            logger.info("snapshot_saved", orders_count=len(all_orders), offsets=offsets)

        # Mirror to durable Postgres storage as a mandatory step: if the
        # durable snapshot cannot be written, the snapshot operation fails so
        # cold-start recovery guarantees are never silently degraded.
        if self.durable_store is not None:
            try:
                await self.durable_store.save(snapshot_data)
            except Exception as e:
                logger.error(
                    "failed_to_save_durable_snapshot", error=str(e), exc_info=True
                )
                raise

    async def load_latest_snapshot(
        self,
    ) -> Tuple[
        List[Order],
        Dict[str, Dict[str, int]],
        Dict[str, Dict[str, dict]],
        Dict[str, int],
    ]:
        """
        Loads the latest snapshot from Redis.
        Returns:
            Tuple[List[Order], offsets_dict, wallets_dict, balance_versions_dict]
        """
        try:
            raw_data = await self.redis.get(self.snapshot_key)
            if not raw_data:
                logger.info("no_snapshot_found_in_redis")
                return [], {}, {}, {}

            snapshot_data = orjson.loads(raw_data)
            offsets = snapshot_data.get("offsets", {})
            orders_data = snapshot_data.get("pending_orders", [])
            wallets_data = snapshot_data.get("wallets", {})
            balance_versions = snapshot_data.get("balance_versions", {})

            orders = [Order.model_validate(data) for data in orders_data]
            logger.info("snapshot_loaded", orders_count=len(orders), offsets=offsets)
            return orders, offsets, wallets_data, balance_versions
        except Exception as e:
            logger.error("failed_to_load_snapshot", error=str(e), exc_info=True)
            # If snapshot is corrupted, return empty to not crash forever,
            # or crash to investigate?
            # Crashing is safer for deterministic recovery.
            raise

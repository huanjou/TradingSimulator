import asyncio
from typing import Dict, List, Tuple

import orjson
import structlog
from app.domain.engine import MatchingEngine
from app.domain.order import Order
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


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
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.snapshot_key = "trading_engine:snapshot"

    async def save_snapshot(
        self, engine: MatchingEngine, offsets: Dict[str, Dict[str, int]]
    ) -> None:
        """
        Saves a snapshot of the engine's pending orders and the latest processed Kafka offsets.
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
                        "locked": str(wallet_info.locked)
                    }

            snapshot_data = {"offsets": offsets, "pending_orders": all_orders, "wallets": wallets_data}

            await self.redis.set(self.snapshot_key, orjson.dumps(snapshot_data))
            logger.info("snapshot_saved", orders_count=len(all_orders), offsets=offsets)
        except Exception as e:
            logger.error("failed_to_save_snapshot", error=str(e), exc_info=True)

    async def load_latest_snapshot(
        self,
    ) -> Tuple[List[Order], Dict[str, Dict[str, int]], Dict[str, Dict[str, dict]]]:
        """
        Loads the latest snapshot from Redis.
        Returns:
            Tuple[List[Order], offsets_dict, wallets_dict]
        """
        try:
            raw_data = await self.redis.get(self.snapshot_key)
            if not raw_data:
                logger.info("no_snapshot_found_in_redis")
                return [], {}, {}

            snapshot_data = orjson.loads(raw_data)
            offsets = snapshot_data.get("offsets", {})
            orders_data = snapshot_data.get("pending_orders", [])
            wallets_data = snapshot_data.get("wallets", {})

            orders = [Order.model_validate(data) for data in orders_data]
            logger.info("snapshot_loaded", orders_count=len(orders), offsets=offsets)
            return orders, offsets, wallets_data
        except Exception as e:
            logger.error("failed_to_load_snapshot", error=str(e), exc_info=True)
            # If snapshot is corrupted, return empty to not crash forever, or crash to investigate?
            # Crashing is safer for deterministic recovery.
            raise

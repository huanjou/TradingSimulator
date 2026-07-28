import asyncio
from decimal import Decimal

import orjson
import structlog
from aiokafka import AIOKafkaConsumer
from app.core.config import settings
from app.core.redis import redis_client
from app.repositories.wallet_repository import WalletRepository
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class BalanceUpdateConsumer:
    def __init__(self):
        self.consumer = None
        self.task = None

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            "balance_updates",
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id="wallet-service-group",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            isolation_level="read_committed",
            session_timeout_ms=10000,
            heartbeat_interval_ms=3000,
        )
        await self.consumer.start()
        logger.info("Kafka Consumer for balance_updates started.")
        self.task = asyncio.create_task(self.consume())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka Consumer stopped.")

    @retry(
        stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def _update_redis(self, repo, user_id, currency, available, locked):
        await repo.update_wallet_balance(user_id, currency, available, locked)

    async def consume(self):
        # We need a repository instance but we can just use the global redis_client
        repo = WalletRepository(redis_client.client)

        while True:
            try:
                async for msg in self.consumer:
                    try:
                        data = orjson.loads(msg.value)
                        user_id = data["user_id"]
                        currency = data["currency"]
                        available = Decimal(data["available"])
                        locked = Decimal(data["locked"])

                        await self._update_redis(
                            repo, user_id, currency, available, locked
                        )
                        await self.consumer.commit()

                        logger.info(
                            f"Updated balance for user {user_id} currency {currency}"
                        )
                    except Exception as e:
                        logger.error(f"Error processing balance update: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer loop failed: {e}. Restarting in 5 seconds...")
                await asyncio.sleep(5)


balance_consumer = BalanceUpdateConsumer()

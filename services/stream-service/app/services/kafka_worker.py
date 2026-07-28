import asyncio

import orjson
import redis.asyncio as redis
import structlog
from aiokafka import AIOKafkaConsumer

from app.core.config import settings

logger = structlog.get_logger(__name__)


class KafkaWorker:
    def __init__(self):
        self.consumer = None
        self.redis_client = None
        self._running = False
        self._consume_task = None

    async def start(self):
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL, decode_responses=False
            )
            # Use consumer group to distribute load among pods
            self.consumer = AIOKafkaConsumer(
                settings.MARKET_DATA_TOPIC,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id="stream-service-group",
                auto_offset_reset="latest",
                # Do not deserialize here, we need raw bytes for Redis
                isolation_level="read_committed",
                session_timeout_ms=10000,
                heartbeat_interval_ms=3000,
            )
            await self.consumer.start()
            self._running = True
            logger.info(
                "KafkaWorker started, connected to Kafka and Redis",
                topic=settings.MARKET_DATA_TOPIC,
            )
            self._consume_task = asyncio.create_task(self._consume())
        except Exception as e:
            logger.error("Failed to start KafkaWorker", error=str(e), exc_info=True)
            raise

    async def stop(self):
        logger.info("Stopping KafkaWorker")
        self._running = False
        if self.consumer:
            await self.consumer.stop()
        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
        if self.redis_client:
            await self.redis_client.aclose()
        logger.info("KafkaWorker stopped")

    def is_healthy(self) -> bool:
        """True while the consume loop is running (used by /health)."""
        return (
            self._running
            and self._consume_task is not None
            and not self._consume_task.done()
        )

    async def _consume(self):
        try:
            async for msg in self.consumer:
                if not self._running:
                    break
                data_bytes = msg.value
                try:
                    # Fast parse to extract symbol
                    parsed = orjson.loads(data_bytes)
                    symbol = parsed.get("symbol")
                    if symbol:
                        channel = f"market_data:{symbol}"
                        # Forward raw bytes to Redis
                        await self.redis_client.publish(channel, data_bytes)
                except (orjson.JSONDecodeError, AttributeError) as e:
                    logger.warning("Invalid message payload", error=str(e))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "Error consuming from Kafka in KafkaWorker", error=str(e), exc_info=True
            )


kafka_worker = KafkaWorker()

import orjson
import structlog
import uuid
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from .config import settings
from typing import Callable, Awaitable

logger = structlog.get_logger(__name__)


class KafkaApp:
    def __init__(self, message_handler: Callable[[list[dict]], Awaitable[None]]):
        self.message_handler = message_handler

        self.consumer = AIOKafkaConsumer(
            settings.KAFKA_ORDERS_TOPIC,
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id="trading-engine-group",
            auto_offset_reset="earliest",
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKER,
            linger_ms=5,
        )

    async def start(self):
        await self.consumer.start()
        await self.producer.start()
        logger.info("kafka_started", topics=[settings.KAFKA_ORDERS_TOPIC])

        try:
            while True:
                # getmany returns dict: {TopicPartition: [ConsumerRecord, ...]}
                data = await self.consumer.getmany(timeout_ms=100, max_records=500)
                if not data:
                    continue

                for tp, messages in data.items():
                    await self._process_batch(messages)
        finally:
            await self.stop()

    async def stop(self):
        await self.consumer.stop()
        await self.producer.stop()
        logger.info("kafka_stopped")

    async def _process_batch(self, messages: list):
        if not messages:
            return

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            batch_id=str(uuid.uuid4()),
            topic=messages[0].topic,
            batch_size=len(messages),
        )
        try:
            orders_data = [orjson.loads(msg.value) for msg in messages]
            logger.info("processing_batch", size=len(orders_data))
            await self.message_handler(orders_data)
        except Exception as e:
            logger.error("batch_processing_failed", error=str(e), exc_info=True)

    async def publish(self, topic: str, data: bytes, key: bytes | None = None):
        """Helper method to expose producer publish functionality. Returns a Future."""
        return await self.producer.send(topic, data, key=key)

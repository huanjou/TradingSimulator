import asyncio
import json
import structlog
import uuid
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from .config import settings
from typing import Callable, Awaitable

logger = structlog.get_logger(__name__)

class KafkaApp:
    def __init__(self, message_handler: Callable[[dict], Awaitable[None]]):
        self.message_handler = message_handler
        
        self.consumer = AIOKafkaConsumer(
            settings.KAFKA_ORDERS_TOPIC,
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id="trading-engine-group",
            auto_offset_reset="earliest"
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKER
        )

    async def start(self):
        await self.consumer.start()
        await self.producer.start()
        logger.info("kafka_started", topics=[settings.KAFKA_ORDERS_TOPIC])
        
        try:
            async for msg in self.consumer:
                await self._process_message(msg)
        finally:
            await self.stop()

    async def stop(self):
        await self.consumer.stop()
        await self.producer.stop()
        logger.info("kafka_stopped")

    async def _process_message(self, msg):
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            batch_id=str(uuid.uuid4()),
            topic=msg.topic,
            partition=msg.partition,
            offset=msg.offset
        )
        try:
            order_data = json.loads(msg.value.decode("utf-8"))
            logger.info("processing_order", order_id=order_data.get("id"))
            await self.message_handler(order_data)
        except Exception as e:
            logger.error("message_processing_failed", error=str(e), exc_info=True)

    async def publish(self, topic: str, data: bytes):
        """Helper method to expose producer publish functionality"""
        await self.producer.send_and_wait(topic, data)

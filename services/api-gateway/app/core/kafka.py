import logging
from typing import Any

import orjson
from aiokafka import AIOKafkaProducer
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class KafkaProducerClient:
    def __init__(self):
        self.producer = None

    async def start(self):
        """Initialize the Kafka producer and connect to the broker."""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKER,
            value_serializer=lambda v: orjson.dumps(v),
            linger_ms=5,
            acks="all",
        )
        await self.producer.start()
        logger.info("Kafka Producer started successfully.")

    async def stop(self):
        """Stop the Kafka producer and flush pending messages."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka Producer stopped.")

    async def send_event(
        self, topic: str, value: dict[str, Any], key: bytes | None = None
    ):
        """Publish an event to a specific Kafka topic."""
        if not self.producer:
            raise RuntimeError("Kafka Producer is not initialized. Call start() first.")

        # Inject current trace context into headers
        from opentelemetry import propagate

        headers_dict = {}
        propagate.inject(headers_dict)
        kafka_headers = [(k, v.encode("utf-8")) for k, v in headers_dict.items()]

        # We await the send coroutine to add to the buffer
        # (it returns a Future for delivery)
        await self.producer.send(topic, value=value, key=key, headers=kafka_headers)
        logger.debug(f"Event published to topic {topic}")


# Global instance
kafka_client = KafkaProducerClient()

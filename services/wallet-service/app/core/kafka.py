import logging
from typing import Any

import orjson
from aiokafka import AIOKafkaProducer
from app.core.config import settings
from opentelemetry import propagate

logger = logging.getLogger(__name__)


class KafkaProducerClient:
    def __init__(self):
        self.producer = None

    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKER,
            value_serializer=lambda v: orjson.dumps(v),
            linger_ms=5,
            acks="all",
        )
        await self.producer.start()
        logger.info("Kafka Producer started successfully.")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka Producer stopped.")

    async def send_command(
        self, topic: str, value: dict[str, Any], key: bytes | None = None
    ):
        if not self.producer:
            raise RuntimeError("Kafka Producer is not initialized. Call start() first.")

        headers_dict = {}
        propagate.inject(headers_dict)
        kafka_headers = [(k, v.encode("utf-8")) for k, v in headers_dict.items()]

        await self.producer.send_and_wait(
            topic, value=value, key=key, headers=kafka_headers
        )
        logger.debug(f"Command published to topic {topic}")


kafka_client = KafkaProducerClient()

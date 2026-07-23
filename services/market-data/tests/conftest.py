import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer


@pytest.fixture
def kafka_broker_url() -> str:
    """Returns the Kafka broker URL, \
    favoring the environment or defaulting to localhost."""
    return os.getenv("KAFKA_BROKER", "localhost:9092")


@pytest_asyncio.fixture
async def kafka_producer(
    kafka_broker_url: str,
) -> AsyncGenerator[AIOKafkaProducer, None]:
    """Provides an active AIOKafkaProducer for sending test messages."""
    producer = AIOKafkaProducer(bootstrap_servers=kafka_broker_url)
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()


@pytest_asyncio.fixture
async def market_data_consumer(
    kafka_broker_url: str,
) -> AsyncGenerator[AIOKafkaConsumer, None]:
    """Provides an AIOKafkaConsumer subscribed to the market_data topic."""
    from app.core.config import settings

    consumer = AIOKafkaConsumer(
        settings.KAFKA_MARKET_DATA_TOPIC,
        bootstrap_servers=kafka_broker_url,
        group_id=f"test-market-data-group-{uuid.uuid4()}",
        auto_offset_reset="latest",
    )
    await consumer.start()
    try:
        yield consumer
    finally:
        await consumer.stop()

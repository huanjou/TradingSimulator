import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from aiokafka import AIOKafkaProducer

os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/1")
os.environ.setdefault("KAFKA_BROKER", "127.0.0.1:9092")
os.environ.setdefault("ENV", "test")


@pytest.fixture
def kafka_broker_url() -> str:
    return os.environ["KAFKA_BROKER"]


@pytest_asyncio.fixture
async def kafka_producer(
    kafka_broker_url: str,
) -> AsyncGenerator[AIOKafkaProducer, None]:
    producer = AIOKafkaProducer(bootstrap_servers=kafka_broker_url)
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

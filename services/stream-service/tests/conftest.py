import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from app.main import app
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def mock_redis():
    with patch("app.services.streamer.redis.from_url") as mock_from_url, patch(
        "app.services.kafka_worker.redis.from_url"
    ) as mock_worker_from_url:
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()

        # pubsub.listen() is an async generator
        async def mock_listen():
            yield {
                "type": "pmessage",
                "channel": b"market_data:BTCUSDT",
                "data": b'{"symbol": "BTCUSDT", "price": "100.0"}',
            }
            while True:
                await asyncio.sleep(1)

        mock_pubsub.listen = mock_listen
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        mock_from_url.return_value = mock_client
        mock_worker_from_url.return_value = mock_client
        yield mock_client


@pytest.fixture(autouse=True)
def mock_kafka():
    with patch("app.services.kafka_worker.AIOKafkaConsumer") as mock_consumer_cls:
        mock_consumer = AsyncMock()

        # AIOKafkaConsumer is an async iterator
        async def mock_anext():
            class MockMessage:
                value = b'{"symbol": "BTCUSDT", "price": "100.0"}'

            yield MockMessage()
            while True:
                await asyncio.sleep(1)

        mock_consumer.__aiter__ = MagicMock(return_value=mock_anext())
        mock_consumer_cls.return_value = mock_consumer
        yield mock_consumer


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

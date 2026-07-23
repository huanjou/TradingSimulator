import asyncio

import pytest
from app.services.kafka_worker import KafkaWorker


@pytest.mark.asyncio
async def test_kafka_worker_lifecycle(mock_redis, mock_kafka):
    worker = KafkaWorker()
    await worker.start()

    assert worker._running is True

    # Wait a bit for the mocked _consume task to process a message
    await asyncio.sleep(0.1)

    # Check that redis.publish was called with correct arguments
    mock_redis.publish.assert_called_with(
        "market_data:BTCUSDT", b'{"symbol": "BTCUSDT", "price": "100.0"}'
    )

    await worker.stop()
    assert worker._running is False

import asyncio

import pytest
from app.services.streamer import StreamManager


@pytest.mark.asyncio
async def test_subscribe_unsubscribe():
    streamer = StreamManager()

    # Test subscribe
    q1 = streamer.subscribe("BTCUSDT")
    q2 = streamer.subscribe("BTCUSDT")

    assert len(streamer.clients["BTCUSDT"]) == 2
    assert q1 in streamer.clients["BTCUSDT"]

    # Test unsubscribe
    streamer.unsubscribe("BTCUSDT", q1)
    assert len(streamer.clients["BTCUSDT"]) == 1

    # Test cleanup of empty sets
    streamer.unsubscribe("BTCUSDT", q2)
    assert "BTCUSDT" not in streamer.clients


@pytest.mark.asyncio
async def test_streamer_lifecycle(mock_redis):
    streamer = StreamManager()
    await streamer.start()

    assert streamer._running is True
    assert streamer.pubsub is not None

    # Subscribe to get messages
    q = streamer.subscribe("BTCUSDT")

    # Wait for the mocked message to arrive
    msg = await asyncio.wait_for(q.get(), timeout=1.0)
    assert msg == b'{"symbol": "BTCUSDT", "price": "100.0"}'

    await streamer.stop()
    assert streamer._running is False

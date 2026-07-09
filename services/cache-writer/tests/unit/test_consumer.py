from unittest.mock import AsyncMock, patch

import pytest

from app.services.consumer import consume


@pytest.mark.asyncio
async def test_consumer_fatal_error_no_commit():
    """
    Test that if process_orders raises a fatal error, the consumer does NOT commit the offset,
    and the exception propagates up to crash the consumer.
    """
    mock_consumer = AsyncMock()

    class MockMessage:
        def __init__(self, offset):
            self.offset = offset

    class MockTopicPartition:
        def __init__(self, topic):
            self.topic = topic

    # Mock getmany to return one batch and then block or fail
    mock_consumer.getmany.return_value = {
        MockTopicPartition(topic="orders"): [MockMessage(offset=10)]
    }

    async def mock_process_orders(messages, **kwargs):
        raise ValueError("Fatal DB Error")

    with patch("app.services.consumer.AIOKafkaConsumer", return_value=mock_consumer):
        with patch(
            "app.services.consumer.process_orders", side_effect=mock_process_orders
        ):
            with pytest.raises(ValueError, match="Fatal DB Error"):
                await consume()

    # Verify that consumer.commit was NEVER called
    mock_consumer.commit.assert_not_called()
    mock_consumer.stop.assert_awaited_once()

from unittest.mock import AsyncMock, MagicMock, patch

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
            self.headers = []

    class MockTopicPartition:
        def __init__(self, topic):
            self.topic = topic
            self.partition = 0

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


@pytest.mark.asyncio
async def test_consumer_extracts_trace_context():
    """
    Test that the consumer extracts trace context from Kafka headers.
    """
    mock_consumer = AsyncMock()

    class MockMessage:
        def __init__(self, offset, headers):
            self.offset = offset
            self.headers = headers

    class MockTopicPartition:
        def __init__(self, topic):
            self.topic = topic
            self.partition = 0

    # Mock getmany to return one batch and then raise an exception to exit the infinite loop
    mock_consumer.getmany.side_effect = [
        {
            MockTopicPartition(topic="orders"): [
                MockMessage(
                    offset=10,
                    headers=[
                        (
                            "traceparent",
                            b"00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
                        )
                    ],
                )
            ]
        },
        ValueError("Exit Loop"),
    ]

    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    with patch("app.services.consumer.AIOKafkaConsumer", return_value=mock_consumer):
        with patch("app.services.consumer.process_orders", new_callable=AsyncMock):
            with patch("opentelemetry.trace.get_tracer", return_value=mock_tracer):
                with pytest.raises(ValueError, match="Exit Loop"):
                    await consume()

    # Verify start_as_current_span was called with links
    mock_tracer.start_as_current_span.assert_called_once()
    kwargs = mock_tracer.start_as_current_span.call_args.kwargs
    assert "links" in kwargs

    # We should have exactly 1 link extracted from the traceparent header
    links = kwargs["links"]
    assert len(links) == 1

    # The trace_id extracted from "0af7651916cd43dd8448eb211c80319c" (hex)
    expected_trace_id = int("0af7651916cd43dd8448eb211c80319c", 16)
    assert links[0].context.trace_id == expected_trace_id

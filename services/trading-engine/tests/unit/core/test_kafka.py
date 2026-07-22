from unittest.mock import AsyncMock, MagicMock

import pytest
from aiokafka import TopicPartition
from app.core.kafka import KafkaConsumerRunner, SeekListener


@pytest.mark.asyncio
async def test_seek_listener():
    # Setup initial offsets
    # For topic "trades", partition 0, the last offset we processed was 100
    initial_offsets = {"trades": {"0": 100}}
    consumer_mock = MagicMock()

    listener = SeekListener(consumer_mock, initial_offsets)

    # We are assigned partition 0 of "trades"
    tp = TopicPartition("trades", 0)

    # Act
    await listener.on_partitions_assigned([tp])

    # Assert we seek to 101 (last_offset + 1)
    consumer_mock.seek.assert_called_once_with(tp, 101)


@pytest.mark.asyncio
async def test_seek_listener_no_initial_offset():
    # Setup empty offsets
    initial_offsets = {}
    consumer_mock = MagicMock()

    listener = SeekListener(consumer_mock, initial_offsets)

    tp = TopicPartition("trades", 0)

    # Act
    await listener.on_partitions_assigned([tp])

    # Assert we do NOT seek if we have no snapshot for this partition
    consumer_mock.seek.assert_not_called()


@pytest.mark.asyncio
async def test_consumer_runner_updates_offsets():
    # Mock handlers
    order_handler = AsyncMock()
    market_data_handler = AsyncMock()

    runner = KafkaConsumerRunner(
        order_handler=order_handler,
        market_data_handler=market_data_handler,
        initial_offsets={},
    )

    # Inject a mocked consumer
    runner.consumer = MagicMock()
    runner.consumer.commit = AsyncMock()

    # Mock some incoming messages
    class MockMsg:
        def __init__(self, topic, partition, offset, value):
            self.topic = topic
            self.partition = partition
            self.offset = offset
            self.value = value
            self.headers = []

    tp1 = TopicPartition("orders", 0)
    msg1 = MockMsg("orders", 0, 50, b'{"id": "1"}')
    msg2 = MockMsg("orders", 0, 51, b'{"id": "2"}')

    batch = {tp1: [msg1, msg2]}

    # Act
    await runner._process_batch(tp1, [msg1, msg2])

    # Assert handlers were called (2 orders)
    assert order_handler.call_count == 1  # Called once with a batch of 2 orders

    # Assert offsets were updated to the max offset of the batch (51)
    assert runner.current_offsets["orders"]["0"] == 51

    # Assert commit was called
    runner.consumer.commit.assert_called_once_with({tp1: 52})

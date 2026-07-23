import asyncio
import json
import uuid
from unittest.mock import AsyncMock

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from app.services.config_consumer import consume_system_events
from app.services.publisher import MarketDataPublisher

from tests.factories import MarketEventFactory


@pytest.mark.integration
@pytest.mark.asyncio
async def test_market_data_publisher_integration(
    kafka_broker_url: str,
):
    """
    Test that the MarketDataPublisher correctly serializes and sends
    a MarketEvent to the real Kafka broker, which can then be consumed.
    """
    test_topic = f"test_market_data_{uuid.uuid4().hex}"

    # 0. Start consumer on the test topic
    consumer = AIOKafkaConsumer(
        test_topic,
        bootstrap_servers=kafka_broker_url,
        group_id=f"test-group-{uuid.uuid4()}",
        auto_offset_reset="earliest",
    )
    await consumer.start()

    # 1. Start publisher
    publisher = MarketDataPublisher(broker_url=kafka_broker_url, topic=test_topic)
    await publisher.start()

    try:
        # 2. Publish a test event
        event = MarketEventFactory.build(
            symbol="TEST/USD", bid_price=3000.5, ask_price=3001.0
        )

        await publisher.publish(event)

        # 3. Read from consumer to verify
        message = await asyncio.wait_for(consumer.getone(), timeout=5.0)

        # 4. Assert message contents
        payload = json.loads(message.value.decode("utf-8"))
        assert payload["symbol"] == "TEST/USD"
        assert payload["bid_price"] == 3000.5
    finally:
        await publisher.stop()
        await consumer.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_config_consumer_integration(
    kafka_producer: AIOKafkaProducer,
    kafka_broker_url: str,
):
    """
    Test that the config consumer reads a system event from Kafka
    and properly calls the provider to update symbols.
    """
    # 1. Create a unique test topic and consumer
    test_topic = f"test_system_events_{uuid.uuid4().hex}"

    consumer = AIOKafkaConsumer(
        test_topic,
        bootstrap_servers=kafka_broker_url,
        group_id=f"test-config-group-{uuid.uuid4().hex}",
        auto_offset_reset="earliest",
    )

    # 2. Mock the provider
    mock_provider = AsyncMock()

    # 3. Run the consumer loop for a short time
    async def run_consumer_briefly():
        try:
            await consume_system_events(consumer, mock_provider)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(run_consumer_briefly())

    # Wait a bit for consumer to start
    await asyncio.sleep(1.0)

    # 4. Send a configuration event to the test topic
    test_symbol = "DOGE/USD"
    event_dict = {"type": "SYMBOL_CREATED", "symbol": test_symbol}

    await kafka_producer.send_and_wait(
        test_topic, value=json.dumps(event_dict).encode("utf-8")
    )

    # Wait for the consumer to process the message (with retry)
    for _ in range(10):
        if mock_provider.add_symbol.call_count > 0:
            break
        await asyncio.sleep(1.0)

    # Cancel the loop
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # 5. Verify the provider was updated
    mock_provider.add_symbol.assert_called_once_with(test_symbol)

import pytest
from app.domain.models import MarketEvent
from app.services.publisher import MarketDataPublisher
from pytest_mock import MockerFixture


@pytest.mark.asyncio
async def test_publisher_start_stop(mocker: MockerFixture):
    mock_producer_cls = mocker.patch("app.services.publisher.AIOKafkaProducer")
    mock_producer = mock_producer_cls.return_value
    mock_producer.start = mocker.AsyncMock()
    mock_producer.stop = mocker.AsyncMock()

    publisher = MarketDataPublisher("localhost:9092", "test_topic")

    await publisher.start()
    mock_producer.start.assert_called_once()

    await publisher.stop()
    mock_producer.stop.assert_called_once()


@pytest.mark.asyncio
async def test_publisher_publish(mocker: MockerFixture):
    mock_producer_cls = mocker.patch("app.services.publisher.AIOKafkaProducer")
    mock_producer = mock_producer_cls.return_value
    mock_producer.send = mocker.AsyncMock()

    publisher = MarketDataPublisher("localhost:9092", "test_topic")
    event = MarketEvent(
        symbol="BTC/USD", bid_price=100.0, ask_price=101.0, timestamp=123456789
    )

    await publisher.publish(event)

    mock_producer.send.assert_called_once_with("test_topic", value=event.model_dump())

    # Also verify the serializer works
    serializer = mock_producer_cls.call_args.kwargs["value_serializer"]
    assert serializer({"a": 1}) == b'{"a":1}'

import asyncio

import pytest
from app.main import main
from pytest_mock import MockerFixture


@pytest.mark.asyncio
async def test_main_graceful_shutdown(mocker: MockerFixture):
    # Mock telemetry to avoid doing OTel exports in tests
    mocker.patch("app.main.setup_telemetry")

    mock_publisher_cls = mocker.patch("app.main.MarketDataPublisher")
    mock_publisher = mock_publisher_cls.return_value
    mock_publisher.start = mocker.AsyncMock()
    mock_publisher.stop = mocker.AsyncMock()

    mock_provider = mocker.Mock()
    mock_provider.close = mocker.AsyncMock()
    mock_consumer = mocker.AsyncMock()

    mocker.patch("app.main.get_provider", return_value=mock_provider)
    mocker.patch("app.main.get_config_consumer", return_value=mock_consumer)

    # consume_system_events runs forever, let's make it sleep
    async def mock_consume(*args, **kwargs):
        await asyncio.sleep(10)

    mocker.patch("app.main.consume_system_events", side_effect=mock_consume)

    # stream_prices yields nothing, then sleeps forever
    async def mock_stream_prices():
        await asyncio.sleep(10)
        yield mocker.Mock()  # won't actually reach here due to sleep

    mock_provider.stream_prices = mock_stream_prices

    # Run main in a task, let it start, then cancel it
    task = asyncio.create_task(main())
    await asyncio.sleep(0.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Publisher should have been started and stopped
    mock_publisher.start.assert_called_once()
    mock_publisher.stop.assert_called_once()

    # Resources should have been closed in the finally block
    mock_provider.close.assert_called_once()
    mock_consumer.stop.assert_called_once()

import orjson
import pytest
from app.services.config_consumer import consume_system_events
from pytest_mock import MockerFixture


@pytest.mark.asyncio
async def test_consume_system_events_success(mocker: MockerFixture):
    mock_consumer = mocker.AsyncMock()
    mock_provider = mocker.AsyncMock()

    # Simulate consumer yielding one message
    mock_msg = mocker.Mock()
    mock_msg.value = orjson.dumps({"type": "SYMBOL_CREATED", "symbol": "SOL/USD"})

    async def mock_aiter():
        yield mock_msg

    mock_consumer.__aiter__.side_effect = mock_aiter

    await consume_system_events(mock_consumer, mock_provider)

    # Verify provider add_symbol was called
    mock_provider.add_symbol.assert_called_once_with("SOL/USD")
    mock_consumer.start.assert_called_once()
    mock_consumer.stop.assert_called_once()


@pytest.mark.asyncio
async def test_consume_system_events_fail_fast(mocker: MockerFixture):
    mock_consumer = mocker.AsyncMock()
    mock_provider = mocker.AsyncMock()

    # Simulate start failing 5 times
    mock_consumer.start.side_effect = Exception("Kafka down")

    # Mock sleep to run fast
    mocker.patch("app.services.config_consumer.asyncio.sleep", return_value=None)

    with pytest.raises(
        RuntimeError, match="Could not connect to Kafka for config consumer"
    ):
        await consume_system_events(mock_consumer, mock_provider)

    assert mock_consumer.start.call_count == 5
    # Since it never started, it should not call stop in this code path


@pytest.mark.asyncio
async def test_consume_system_events_invalid_json_or_unknown_type(
    mocker: MockerFixture,
):
    mock_consumer = mocker.AsyncMock()
    mock_provider = mocker.AsyncMock()

    msg1 = mocker.Mock(value=b"invalid json")
    msg2 = mocker.Mock(value=orjson.dumps({"type": "UNKNOWN_EVENT", "symbol": "BTC"}))

    async def mock_aiter():
        yield msg1
        yield msg2

    mock_consumer.__aiter__.side_effect = mock_aiter

    await consume_system_events(mock_consumer, mock_provider)

    # Provider should not have been called
    mock_provider.add_symbol.assert_not_called()
    mock_consumer.stop.assert_called_once()

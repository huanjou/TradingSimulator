import asyncio
import json

import pytest
import websockets
import websockets.exceptions
from app.providers.binance import BinanceMarketDataProvider
from pytest_mock import MockerFixture


@pytest.fixture
def provider():
    return BinanceMarketDataProvider(symbols=["BTC/USD"])


@pytest.mark.asyncio
async def test_add_symbol_success(provider, mocker: MockerFixture):
    provider._ws = mocker.AsyncMock()

    await provider.add_symbol("ETH/USD")

    assert "ETH/USD" in provider.symbols
    expected_payload = {
        "method": "SUBSCRIBE",
        "params": ["ethusdt@bookTicker"],
        "id": 2,
    }
    provider._ws.send.assert_called_once_with(json.dumps(expected_payload))


@pytest.mark.asyncio
async def test_add_symbol_connection_closed(provider, mocker: MockerFixture):
    provider._ws = mocker.AsyncMock()
    provider._ws.send.side_effect = websockets.exceptions.ConnectionClosedError(
        None, None
    )

    # Should not raise exception
    await provider.add_symbol("ETH/USD")
    assert "ETH/USD" in provider.symbols


@pytest.mark.asyncio
async def test_stream_prices_success(provider, mocker: MockerFixture):
    mock_ws = mocker.AsyncMock()

    # Simulate a stream of 2 messages
    mock_ws.__aiter__.return_value = [
        json.dumps({"s": "BTCUSDT", "b": "100.0", "a": "101.0", "E": 12345}),
        json.dumps({"s": "BTCUSDT", "b": "100.5", "a": "101.5", "E": 12346}),
    ]

    mock_connect_cls = mocker.patch("app.providers.binance.websockets.connect")
    mock_connect_instance = mock_connect_cls.return_value
    mock_connect_instance.__aenter__.return_value = mock_ws

    events = []

    # stream_prices has a `while True`, so we need to cancel it after reading 2 events
    # actually a better way to test async generator is:
    events = []
    try:
        async for evt in provider.stream_prices():
            events.append(evt)
            if len(events) == 2:
                break
    except StopAsyncIteration:
        pass

    assert len(events) == 2
    assert events[0].symbol == "BTC/USD"
    assert events[0].bid_price == 100.0
    assert events[0].ask_price == 101.0

    # Verify initial subscribe payload was sent
    assert mock_ws.send.call_count >= 1


@pytest.mark.asyncio
async def test_stream_prices_skips_invalid_data(provider, mocker: MockerFixture):
    mock_ws = mocker.AsyncMock()

    mock_ws.__aiter__.return_value = [
        "invalid json format",
        json.dumps({"result": "subscribe success"}),
        json.dumps({"s": "BTCUSDT"}),  # missing a and b
        json.dumps({"s": "BTCUSDT", "b": "100.0", "a": "101.0", "E": 12345}),
    ]

    mock_connect_cls = mocker.patch("app.providers.binance.websockets.connect")
    mock_connect_instance = mock_connect_cls.return_value
    mock_connect_instance.__aenter__.return_value = mock_ws

    events = []
    try:
        async for evt in provider.stream_prices():
            events.append(evt)
            if len(events) == 1:
                break
    except StopAsyncIteration:
        pass

    assert len(events) == 1
    assert events[0].symbol == "BTC/USD"


@pytest.mark.asyncio
async def test_add_symbol_ws_none(provider):
    # Should not raise exception
    await provider.add_symbol("ETH/USD")
    assert "ETH/USD" in provider.symbols


@pytest.mark.asyncio
async def test_close(provider, mocker: MockerFixture):
    provider._ws = mocker.AsyncMock()
    await provider.close()
    provider._ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_stream_prices_exponential_backoff(provider, mocker: MockerFixture):
    mock_connect = mocker.patch("app.providers.binance.websockets.connect")
    mock_connect.side_effect = Exception("Connection refused")

    mock_sleep = mocker.patch("app.providers.binance.asyncio.sleep")

    # stream_prices runs forever. Let's patch sleep
    # to raise CancelledError after 3 calls
    # so we can observe the backoff delays.

    sleep_calls = []

    async def mock_sleep_impl(delay):
        sleep_calls.append(delay)
        if len(sleep_calls) == 3:
            raise asyncio.CancelledError()

    mock_sleep.side_effect = mock_sleep_impl

    with pytest.raises(asyncio.CancelledError):
        # We need to iterate it to make it run
        async for _ in provider.stream_prices():
            pass

    assert sleep_calls == [1.0, 2.0, 4.0]

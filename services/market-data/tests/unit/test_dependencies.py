import httpx
import pytest
from app.core.config import settings
from app.core.dependencies import fetch_config, get_config_consumer, get_provider
from app.providers.binance import BinanceMarketDataProvider
from pytest_mock import MockerFixture


@pytest.mark.asyncio
async def test_fetch_config_success(mocker: MockerFixture):
    mock_response = mocker.Mock()
    mock_response.json.return_value = [
        {"name": "BTC/USD", "is_active": True},
        {"name": "ETH/USD", "is_active": True},
        {"name": "SOL/USD", "is_active": False},
    ]
    mock_response.raise_for_status.return_value = None

    mock_client = mocker.AsyncMock()
    mock_client.get.return_value = mock_response

    # Mock the context manager __aenter__ to return our mock_client
    mock_async_client_cls = mocker.patch("app.core.dependencies.httpx.AsyncClient")
    mock_async_client_instance = mock_async_client_cls.return_value
    mock_async_client_instance.__aenter__.return_value = mock_client

    symbols = await fetch_config()

    assert symbols == ["BTC/USD", "ETH/USD"]
    mock_client.get.assert_called_once_with(
        f"{settings.QUERY_SERVICE_URL.rstrip('/')}/api/v1/symbols"
    )


@pytest.mark.asyncio
async def test_fetch_config_fallback_on_error(mocker: MockerFixture):
    mock_client = mocker.AsyncMock()
    mock_client.get.side_effect = httpx.TimeoutException("Timeout")

    mock_async_client_cls = mocker.patch("app.core.dependencies.httpx.AsyncClient")
    mock_async_client_instance = mock_async_client_cls.return_value
    mock_async_client_instance.__aenter__.return_value = mock_client

    # Set up ENV fallback
    settings.MARKET_SYMBOLS = "XRP/USD, ADA/USD"

    symbols = await fetch_config()

    assert symbols == ["XRP/USD", "ADA/USD"]


@pytest.mark.asyncio
async def test_get_provider(mocker: MockerFixture):
    mocker.patch("app.core.dependencies.fetch_config", return_value=["DOGE/USD"])
    settings.MARKET_PROVIDER = "binance"

    provider = await get_provider()

    assert isinstance(provider, BinanceMarketDataProvider)


@pytest.mark.asyncio
async def test_get_provider_unknown(mocker: MockerFixture):
    mocker.patch("app.core.dependencies.fetch_config", return_value=["BTC/USD"])
    settings.MARKET_PROVIDER = "unknown_provider"

    with pytest.raises(ValueError, match="Unknown market provider: unknown_provider"):
        await get_provider()


@pytest.mark.asyncio
async def test_get_provider_empty_symbols(mocker: MockerFixture):
    mocker.patch("app.core.dependencies.fetch_config", return_value=[])
    settings.MARKET_PROVIDER = "binance"

    provider = await get_provider()
    assert provider.symbols == ["BTC/USD"]


def test_get_config_consumer(mocker: MockerFixture):
    mock_consumer_cls = mocker.patch("aiokafka.AIOKafkaConsumer")
    consumer = get_config_consumer()
    assert consumer == mock_consumer_cls.return_value
    mock_consumer_cls.assert_called_once_with(
        "system_events",
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id="market-data-group",
        auto_offset_reset="latest",
    )

from typing import TYPE_CHECKING

import requests
import structlog

if TYPE_CHECKING:
    from aiokafka import AIOKafkaConsumer
from app.core.config import settings
from app.providers.base import MarketDataProvider
from app.providers.binance import BinanceMarketDataProvider

logger = structlog.get_logger(__name__)


def fetch_config() -> list[str]:
    """Fetches active symbols from query-service, falls back to ENV"""
    try:
        url = f"{settings.QUERY_SERVICE_URL.rstrip('/')}/api/v1/symbols"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        symbols = [s["name"] for s in data if s["is_active"]]
        logger.info("Fetched symbols from query-service", symbols=symbols)
        return symbols
    except Exception as e:
        logger.warning(
            "Could not fetch symbols from query-service, falling back to ENV",
            error=str(e),
        )
        return [s.strip() for s in settings.MARKET_SYMBOLS.split(",") if s.strip()]


def get_provider() -> MarketDataProvider:
    """Factory method to get the configured market data provider."""
    symbols = fetch_config()
    if not symbols:
        symbols = ["BTC/USD"]

    if settings.MARKET_PROVIDER.lower() == "binance":
        return BinanceMarketDataProvider(symbols=symbols)
    else:
        raise ValueError(f"Unknown market provider: {settings.MARKET_PROVIDER}")


def get_config_consumer() -> "AIOKafkaConsumer":
    """Factory method to get the consumer for system events."""
    from aiokafka import AIOKafkaConsumer

    return AIOKafkaConsumer(
        "system_events",
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id="market-data-group",
        auto_offset_reset="latest",
    )

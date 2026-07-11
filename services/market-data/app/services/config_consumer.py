import asyncio
import orjson
import structlog
from aiokafka import AIOKafkaConsumer

from app.providers.base import MarketDataProvider

logger = structlog.get_logger(__name__)


async def consume_system_events(
    consumer: AIOKafkaConsumer, provider: MarketDataProvider
):
    """
    Listens to system_events for SYMBOL_CREATED and dynamically updates the market data provider.
    """
    # Try connecting, with retries
    for attempt in range(5):
        try:
            await consumer.start()
            logger.info("system_events consumer started")
            break
        except Exception as e:
            logger.error(
                "Failed to start config consumer", error=str(e), attempt=attempt
            )
            await asyncio.sleep(5)
    else:
        logger.error("Could not connect to Kafka for config consumer")
        return

    try:
        async for msg in consumer:
            try:
                data = orjson.loads(msg.value)
                if data.get("type") == "SYMBOL_CREATED":
                    symbol = data.get("symbol")
                    if symbol:
                        logger.info("Received dynamic symbol addition", symbol=symbol)
                        await provider.add_symbol(symbol)
            except Exception as e:
                logger.error("Error processing system event", error=str(e))
    finally:
        await consumer.stop()

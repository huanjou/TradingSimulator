import asyncio

import structlog
from app.core.config import settings
from app.core.dependencies import get_config_consumer, get_provider
from app.core.telemetry import setup_telemetry
from app.services.config_consumer import consume_system_events
from app.services.publisher import MarketDataPublisher

logger = structlog.get_logger(__name__)


async def main():
    setup_telemetry("market-data")
    logger.info("Starting market-data service", provider=settings.MARKET_PROVIDER)

    publisher = MarketDataPublisher(
        broker_url=settings.KAFKA_BROKER, topic=settings.KAFKA_MARKET_DATA_TOPIC
    )
    await publisher.start()

    while True:
        try:
            # We initialize the provider inside the loop so that if it crashes completely,  # noqa: E501
            # we can fetch fresh config and restart it
            provider = get_provider()
            consumer = get_config_consumer()

            consumer_task = asyncio.create_task(
                consume_system_events(consumer, provider)
            )

            async for event in provider.stream_prices():
                await publisher.publish(event)

        except asyncio.CancelledError:
            logger.info("Service shutting down gracefully")
            consumer_task.cancel()
            break
        except Exception as e:
            logger.error(
                "Unhandled error in main loop. Restarting in 5s...", error=str(e)
            )
            consumer_task.cancel()
            await asyncio.sleep(5)

    await publisher.stop()


if __name__ == "__main__":
    asyncio.run(main())

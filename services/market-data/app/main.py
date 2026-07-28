import asyncio
import signal

import structlog
from app.core.config import settings
from app.core.dependencies import get_config_consumer, get_provider
from app.core.health import HealthServer
from app.core.telemetry import setup_telemetry
from app.services.config_consumer import consume_system_events
from app.services.publisher import MarketDataPublisher

logger = structlog.get_logger(__name__)


def install_signal_handlers(shutdown_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, shutdown_event.set)
        except NotImplementedError:
            # Windows: fall back to sync signal handlers
            signal.signal(sig, lambda *_: shutdown_event.set())


async def run(publisher: MarketDataPublisher):
    while True:
        provider = None
        consumer = None
        try:
            # We initialize the provider inside the loop
            # so that if it crashes completely,
            # we can fetch fresh config and restart it
            provider = await get_provider()
            consumer = get_config_consumer()

            async def run_price_stream(current_provider):
                async for event in current_provider.stream_prices():
                    await publisher.publish(event)

            async with asyncio.TaskGroup() as tg:
                tg.create_task(consume_system_events(consumer, provider))
                tg.create_task(run_price_stream(provider))

        except asyncio.CancelledError:
            logger.info("Service shutting down gracefully")
            break
        except Exception as e:
            logger.error(
                "Unhandled error in main loop. Restarting in 5s...", error=str(e)
            )
            await asyncio.sleep(5)
        finally:
            if provider:
                await provider.close()
            if consumer:
                await consumer.stop()


async def main():
    setup_telemetry("market-data")
    logger.info("Starting market-data service", provider=settings.MARKET_PROVIDER)

    shutdown_event = asyncio.Event()
    install_signal_handlers(shutdown_event)

    publisher = MarketDataPublisher(
        broker_url=settings.KAFKA_BROKER, topic=settings.KAFKA_MARKET_DATA_TOPIC
    )
    await publisher.start()

    run_task = asyncio.create_task(run(publisher))

    async def health_checks() -> dict[str, str]:
        checks = {}
        # Check Kafka: cheap metadata fetch through the producer client
        try:
            await publisher.producer.client.fetch_all_metadata()
            checks["kafka"] = "ok"
        except Exception:
            checks["kafka"] = "error"
        return checks

    health_server = HealthServer(health_checks, port=settings.HEALTH_PORT)
    await health_server.start()

    # Run until SIGTERM/SIGINT or until the run loop dies on its own
    shutdown_wait = asyncio.create_task(shutdown_event.wait())
    try:
        await asyncio.wait(
            [run_task, shutdown_wait], return_when=asyncio.FIRST_COMPLETED
        )
    except asyncio.CancelledError:
        pass
    finally:
        shutdown_wait.cancel()

        logger.info("Shutting down gracefully...")
        try:
            async with asyncio.timeout(10):
                run_task.cancel()
                await asyncio.gather(run_task, return_exceptions=True)
                await health_server.stop()
                await publisher.stop()
        except TimeoutError:
            logger.warning("graceful_shutdown_timed_out")
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

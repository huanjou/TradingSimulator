import asyncio
import signal

import structlog
from app.core.config import get_settings
from app.core.health import HealthServer
from app.core.logging import setup_logging
from app.core.telemetry import setup_opentelemetry
from app.db.base import Base  # noqa: F401 (Ensure models are registered)
from app.db.session import engine
from app.services.consumer import consume
from sqlalchemy import text

settings = get_settings()
logger = structlog.get_logger(__name__)


def install_signal_handlers(shutdown_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, shutdown_event.set)
        except NotImplementedError:
            # Windows: fall back to sync signal handlers
            signal.signal(sig, lambda *_: shutdown_event.set())


async def main():
    shutdown_event = asyncio.Event()
    install_signal_handlers(shutdown_event)

    consume_task = asyncio.create_task(consume(shutdown_event))

    async def health_checks() -> dict[str, str]:
        checks = {}
        # Kafka: the consume loop must still be alive
        checks["kafka"] = "ok" if not consume_task.done() else "error"
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["postgres"] = "ok"
        except Exception:
            checks["postgres"] = "error"
        return checks

    health_server = HealthServer(health_checks, port=settings.HEALTH_PORT)
    await health_server.start()

    # Run until SIGTERM/SIGINT or until the consumer dies on its own
    shutdown_wait = asyncio.create_task(shutdown_event.wait())
    await asyncio.wait(
        [consume_task, shutdown_wait], return_when=asyncio.FIRST_COMPLETED
    )
    shutdown_wait.cancel()

    logger.info("Shutting down gracefully...")
    try:
        # Let the in-flight batch finish and commit its offsets, then the
        # consume loop exits and stops the consumer in its finally block.
        await asyncio.wait_for(
            asyncio.gather(consume_task, return_exceptions=True), timeout=10
        )
    except TimeoutError:
        logger.warning("graceful_shutdown_timed_out")
        consume_task.cancel()
        await asyncio.gather(consume_task, return_exceptions=True)
    await health_server.stop()
    await engine.dispose()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    setup_logging(log_level=settings.LOG_LEVEL)
    setup_opentelemetry()
    asyncio.run(main())

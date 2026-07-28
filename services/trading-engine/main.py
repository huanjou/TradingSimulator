import asyncio
import signal

import structlog
from app.core.config import settings
from app.core.health import HealthServer
from app.core.kafka import KafkaConsumerRunner, KafkaPublisher
from app.core.logging import setup_logging
from app.core.telemetry import setup_opentelemetry
from app.domain.engine import MatchingEngine
from app.services.durable_snapshot import DurableSnapshotStore
from app.services.matching_service import MatchingService
from app.services.snapshot_service import SnapshotManager, periodic_snapshot_task
from redis.asyncio import Redis

setup_logging()
setup_opentelemetry()
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

    engine = MatchingEngine()
    redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=10,
    )

    # Durable snapshot mirror (Postgres). Optional: only when POSTGRES_URL is set.
    durable_store = None
    if settings.POSTGRES_URL:
        durable_store = DurableSnapshotStore(settings.POSTGRES_URL)
        await durable_store.connect()
        await durable_store.ensure_schema()

    snapshot_manager = SnapshotManager(redis_client, durable_store=durable_store)

    # Recover state (Fail Fast: let it raise Exception if it fails)
    logger.info("recovering_pending_orders_from_snapshot")
    (
        pending_orders,
        initial_offsets,
        wallets_data,
        balance_versions,
    ) = await snapshot_manager.load_latest_snapshot()

    # Layered cold-start recovery (Redis snapshot was absent):
    #   1. Durable Postgres snapshot -> exact offsets paired atomically with the
    #      state, so we resume from the precise position (normal seek, NO
    #      seek_to_end, no in-flight loss).
    #   2. CQRS ledger rehydration -> approximate state + seek_to_end. Last
    #      resort; can miss in-flight commands but never starts from empty
    #      (which would let the next absolute balance_update wipe the ledger).
    seek_to_end = False
    cold_start = not initial_offsets and not pending_orders and not wallets_data

    if cold_start and durable_store is not None:
        d_orders, d_offsets, d_wallets, d_versions = await durable_store.load()
        if d_offsets or d_orders or d_wallets:
            logger.warning("recovered_from_durable_postgres_snapshot")
            pending_orders, initial_offsets, wallets_data, balance_versions = (
                d_orders,
                d_offsets,
                d_wallets,
                d_versions,
            )
            cold_start = False

    if cold_start and settings.POSTGRES_URL:
        logger.warning("no_snapshot_found_rehydrating_from_cqrs_ledger")
        from app.services.rehydration_service import load_state_from_db

        wallets_data, pending_orders = await load_state_from_db(settings.POSTGRES_URL)
        if wallets_data or pending_orders:
            # The ledger has prior state -> skip the historical backlog.
            seek_to_end = True
    elif cold_start:
        logger.warning("no_snapshot_and_no_postgres_url_starting_empty")

    engine.restore_orders(pending_orders)
    engine.restore_wallets(wallets_data)
    engine.restore_balance_versions(balance_versions)

    publisher = KafkaPublisher()

    service = MatchingService(
        engine=engine,
        publisher=publisher,
        trades_topic=settings.KAFKA_TRADES_TOPIC,
        updates_topic=settings.KAFKA_ORDER_UPDATES_TOPIC,
        balance_updates_topic=settings.KAFKA_BALANCE_UPDATES_TOPIC,
    )

    consumer = KafkaConsumerRunner(
        order_handler=service.handle_orders_batch,
        market_data_handler=service.handle_market_data_batch,
        wallet_commands_handler=service.handle_wallet_commands_batch,
        initial_offsets=initial_offsets,
        seek_to_end=seek_to_end,
    )

    # Start periodic snapshotting
    snapshot_task = asyncio.create_task(
        periodic_snapshot_task(snapshot_manager, engine, consumer)
    )

    logger.info("Starting Trading Engine...")
    await publisher.start()
    consumer_task = asyncio.create_task(consumer.start())

    async def health_checks() -> dict[str, str]:
        checks = {}
        # Kafka: the consume loop must still be alive
        checks["kafka"] = "ok" if not consumer_task.done() else "error"
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
        if durable_store is not None:
            try:
                await durable_store.ping()
                checks["postgres"] = "ok"
            except Exception:
                checks["postgres"] = "error"
        return checks

    health_server = HealthServer(health_checks, port=settings.HEALTH_PORT)
    await health_server.start()

    # Run until SIGTERM/SIGINT or until the consumer dies on its own
    shutdown_wait = asyncio.create_task(shutdown_event.wait())
    await asyncio.wait(
        [consumer_task, shutdown_wait], return_when=asyncio.FIRST_COMPLETED
    )
    shutdown_wait.cancel()

    logger.info("Shutting down gracefully...")
    try:
        async with asyncio.timeout(10):
            # 1. Stop consuming new messages (offsets are committed per batch,
            #    consumer.stop() runs in the task's finally block)
            consumer_task.cancel()
            await asyncio.gather(consumer_task, return_exceptions=True)
            # 2. Stop periodic snapshotting
            snapshot_task.cancel()
            await asyncio.gather(snapshot_task, return_exceptions=True)
            # 3. Flush pending events and close connections
            await publisher.stop()
            await health_server.stop()
            await redis_client.close()
            if durable_store is not None:
                await durable_store.close()
    except TimeoutError:
        logger.warning("graceful_shutdown_timed_out")
    logger.info("Trading Engine stopped")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio

import structlog
from app.core.config import settings
from app.core.kafka import KafkaConsumerRunner, KafkaPublisher
from app.core.logging import setup_logging
from app.core.telemetry import setup_opentelemetry
from app.domain.engine import MatchingEngine
from app.services.matching_service import MatchingService
from app.services.snapshot_service import SnapshotManager, periodic_snapshot_task
from redis.asyncio import Redis

setup_logging()
setup_opentelemetry()
logger = structlog.get_logger(__name__)


async def main():
    engine = MatchingEngine()
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    snapshot_manager = SnapshotManager(redis_client)

    # Recover state (Fail Fast: let it raise Exception if it fails)
    logger.info("recovering_pending_orders_from_snapshot")
    pending_orders, initial_offsets, wallets_data = await snapshot_manager.load_latest_snapshot()
    engine.restore_orders(pending_orders)
    engine.restore_wallets(wallets_data)

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
    )

    # Start periodic snapshotting
    snapshot_task = asyncio.create_task(
        periodic_snapshot_task(snapshot_manager, engine, consumer)
    )

    logger.info("Starting Trading Engine...")
    try:
        await publisher.start()
        await consumer.start()
    except asyncio.CancelledError:
        logger.info("Trading Engine cancelled")
    except KeyboardInterrupt:
        logger.info("Trading Engine interrupted by user")
    finally:
        snapshot_task.cancel()
        await consumer.stop()
        await publisher.stop()
        await redis_client.close()
        logger.info("Trading Engine stopped")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio

from app.core.kafka import KafkaApp
from app.domain.engine import MatchingEngine

import structlog
from app.core.logging import setup_logging

from app.core.telemetry import setup_opentelemetry

setup_logging()
setup_opentelemetry()
logger = structlog.get_logger(__name__)


async def fetch_pending_orders(engine: MatchingEngine):
    import httpx
    from app.core.config import settings
    from app.domain.order import Order

    url = f"{settings.QUERY_SERVICE_URL.rstrip('/')}/api/v1/orders/pending"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            orders_data = response.json()

            count = 0
            for data in orders_data:
                order = Order.model_validate(data)
                if order.symbol not in engine.pending_orders:
                    engine.pending_orders[order.symbol] = []
                engine.pending_orders[order.symbol].append(order)
                count += 1
            logger.info("recovered_pending_orders_from_db", count=count)
    except Exception as e:
        logger.error("failed_to_recover_pending_orders", error=str(e))


async def main():
    engine = MatchingEngine()

    # Recover state
    await fetch_pending_orders(engine)
    # However, in python, we can just instantiate it with None and set it,
    # or instantiate KafkaApp with a forward reference.
    # Actually, KafkaApp expects a message_handler in its init.
    # MatchingService expects a publisher.

    class PublisherAdapter:
        def __init__(self):
            self.kafka_app = None

        async def publish(self, topic: str, data: bytes, key: bytes | None = None):
            if self.kafka_app:
                return await self.kafka_app.publish(topic, data, key=key)

    adapter = PublisherAdapter()

    from app.services.matching_service import MatchingService
    from app.core.config import settings

    service = MatchingService(
        engine=engine,
        publisher=adapter,
        trades_topic=settings.KAFKA_TRADES_TOPIC,
        updates_topic=settings.KAFKA_ORDER_UPDATES_TOPIC,
    )

    app = KafkaApp(
        order_handler=service.handle_orders_batch,
        market_data_handler=service.handle_market_data_batch,
    )
    adapter.kafka_app = app

    logger.info("Starting Trading Engine...")
    try:
        await app.start()
    except asyncio.CancelledError:
        logger.info("Trading Engine cancelled")
    except KeyboardInterrupt:
        logger.info("Trading Engine interrupted by user")
    finally:
        logger.info("Trading Engine stopped")


if __name__ == "__main__":
    asyncio.run(main())

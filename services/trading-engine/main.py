import asyncio

import sys
from app.core.kafka import KafkaApp
from app.domain.engine import MatchingEngine

import structlog
from app.core.logging import setup_logging

setup_logging()
logger = structlog.get_logger(__name__)

async def main():
    engine = MatchingEngine()
    
    # Instantiate the Kafka app first but don't start it yet
    # We need it to pass to the matching service
    # However, in python, we can just instantiate it with None and set it,
    # or instantiate KafkaApp with a forward reference.
    # Actually, KafkaApp expects a message_handler in its init.
    # MatchingService expects a publisher.
    
    class PublisherAdapter:
        def __init__(self):
            self.kafka_app = None
            
        async def publish(self, topic: str, data: bytes):
            if self.kafka_app:
                await self.kafka_app.publish(topic, data)

    adapter = PublisherAdapter()
    
    from app.services.matching_service import MatchingService
    from app.core.config import settings
    
    service = MatchingService(
        engine=engine,
        publisher=adapter,
        trades_topic=settings.KAFKA_TRADES_TOPIC,
        updates_topic=settings.KAFKA_ORDER_UPDATES_TOPIC
    )
    
    app = KafkaApp(message_handler=service.handle_new_order)
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

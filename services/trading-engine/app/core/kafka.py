import asyncio
import json
import logging
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from app.core.config import settings
from app.domain.engine import MatchingEngine
from app.domain.order import Order

logger = logging.getLogger(__name__)

class KafkaApp:
    def __init__(self, engine: MatchingEngine):
        self.engine = engine
        self.consumer = AIOKafkaConsumer(
            settings.KAFKA_ORDERS_TOPIC,
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id="trading-engine-group",
            auto_offset_reset="earliest"
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKER
        )

    async def start(self):
        await self.consumer.start()
        await self.producer.start()
        logger.info("Kafka consumer and producer started")
        
        try:
            async for msg in self.consumer:
                await self._process_message(msg)
        finally:
            await self.stop()

    async def stop(self):
        await self.consumer.stop()
        await self.producer.stop()
        logger.info("Kafka consumer and producer stopped")

    async def _process_message(self, msg):
        try:
            order_data = json.loads(msg.value.decode("utf-8"))
            order = Order.model_validate(order_data)
            
            # Process order through the matching engine
            trades = self.engine.process_order(order)
            
            # Publish trades
            for trade in trades:
                trade_json = trade.model_dump_json().encode("utf-8")
                await self.producer.send_and_wait(
                    settings.KAFKA_TRADES_TOPIC, 
                    trade_json
                )
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")

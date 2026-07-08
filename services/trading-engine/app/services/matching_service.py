import json
import structlog
from typing import Protocol
from app.domain.engine import MatchingEngine
from app.domain.order import Order

logger = structlog.get_logger(__name__)

class MessagePublisher(Protocol):
    async def publish(self, topic: str, message: bytes) -> None:
        pass

class MatchingService:
    def __init__(self, engine: MatchingEngine, publisher: MessagePublisher, trades_topic: str, updates_topic: str):
        self.engine = engine
        self.publisher = publisher
        self.trades_topic = trades_topic
        self.updates_topic = updates_topic

    async def handle_new_order(self, order_data: dict) -> None:
        try:
            # 1. Convert to domain model
            order = Order.model_validate(order_data)
            
            # 2. Execute business logic
            trades, updates = self.engine.process_order(order)
            
            # 3. Publish results
            for trade in trades:
                trade_bytes = trade.model_dump_json().encode("utf-8")
                await self.publisher.publish(self.trades_topic, trade_bytes)
                logger.info("trade_published", trade_id=str(trade.trade_id), maker_order_id=str(trade.maker_order_id), taker_order_id=str(trade.taker_order_id))
                
            for update in updates:
                update_bytes = update.model_dump_json().encode("utf-8")
                await self.publisher.publish(self.updates_topic, update_bytes)
                logger.info("order_update_published", order_id=str(update.order_id), status=update.status.value)
                
        except Exception as e:
            logger.error("order_handling_failed", error=str(e), exc_info=True)

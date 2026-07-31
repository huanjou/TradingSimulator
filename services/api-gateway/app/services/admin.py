import structlog
from app.core.config import get_settings
from app.core.kafka import KafkaProducerClient
from app.domain.system_event import SystemEvent, SystemEventType

logger = structlog.get_logger(__name__)
settings = get_settings()


class AdminService:
    def __init__(self, kafka_client: KafkaProducerClient):
        self.kafka_client = kafka_client

    async def create_symbol(self, symbol: str) -> str:
        """
        Publishes a SYMBOL_CREATED event to the system_events topic.
        """
        event = SystemEvent(
            type=SystemEventType.SYMBOL_CREATED,
            symbol=symbol,
        )

        try:
            # We await send_event which with
            # wait_for_ack=True handles synchronous propagation
            await self.kafka_client.send_event(
                topic="system_events", value=event.model_dump(), wait_for_ack=True
            )
            logger.info(
                "Published SYMBOL_CREATED event", symbol=symbol, event_id=event.event_id
            )
            return event.event_id
        except Exception as e:
            logger.error(
                "Failed to publish SYMBOL_CREATED event", symbol=symbol, error=str(e)
            )
            raise

import structlog
from aiokafka import AIOKafkaProducer
from app.core.config import get_settings
from app.domain.system_event import SystemEvent, SystemEventType

logger = structlog.get_logger(__name__)
settings = get_settings()


class AdminService:
    def __init__(self, producer: AIOKafkaProducer):
        self.producer = producer

    async def create_symbol(self, symbol: str) -> str:
        """
        Publishes a SYMBOL_CREATED event to the system_events topic.
        """
        event = SystemEvent(
            type=SystemEventType.SYMBOL_CREATED,
            symbol=symbol,
        )

        try:
            await self.producer.send_and_wait("system_events", value=event.model_dump())
            logger.info(
                "Published SYMBOL_CREATED event", symbol=symbol, event_id=event.event_id
            )
            return event.event_id
        except Exception as e:
            logger.error(
                "Failed to publish SYMBOL_CREATED event", symbol=symbol, error=str(e)
            )
            raise

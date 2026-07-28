import orjson
import structlog
from aiokafka import AIOKafkaProducer
from app.domain.models import MarketEvent

logger = structlog.get_logger(__name__)


class MarketDataPublisher:
    def __init__(self, broker_url: str, topic: str):
        self.broker_url = broker_url
        self.topic = topic
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.broker_url,
            value_serializer=lambda v: orjson.dumps(v),
            acks="all",
        )

    async def start(self):
        await self.producer.start()
        logger.info("Kafka producer started", broker=self.broker_url)

    async def stop(self):
        await self.producer.stop()
        logger.info("Kafka producer stopped")

    async def publish(self, event: MarketEvent):
        await self.producer.send(self.topic, value=event.model_dump())

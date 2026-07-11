import asyncio
import orjson
import structlog
from aiokafka import AIOKafkaConsumer

from app.core.config import settings

logger = structlog.get_logger(__name__)


class KafkaStreamer:
    def __init__(self):
        self.consumer = None
        self._running = False
        self.clients = set()

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            settings.MARKET_DATA_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id="stream-service-group",
            auto_offset_reset="latest",
            value_deserializer=lambda v: orjson.loads(v),
        )
        await self.consumer.start()
        self._running = True
        logger.info("Kafka consumer started", topic=settings.MARKET_DATA_TOPIC)
        asyncio.create_task(self._consume())

    async def stop(self):
        self._running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")

    async def _consume(self):
        try:
            async for msg in self.consumer:
                if not self._running:
                    break
                data = msg.value
                # Broadcast to all connected clients
                for q in list(self.clients):
                    try:
                        q.put_nowait(data)
                    except asyncio.QueueFull:
                        pass  # Drop if client is too slow
        except Exception as e:
            logger.error("Error consuming market data", error=str(e))

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self.clients.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self.clients:
            self.clients.remove(q)


kafka_streamer = KafkaStreamer()

import asyncio
from collections import defaultdict

import redis.asyncio as redis
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class StreamManager:
    def __init__(self):
        self.redis_client = None
        self.pubsub = None
        self._running = False
        self._consume_task = None
        # symbol -> set(asyncio.Queue)
        self.clients = defaultdict(set)

    async def start(self):
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL, decode_responses=False
            )
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.psubscribe("market_data:*")
            self._running = True
            logger.info("StreamManager started, connected to Redis")
            self._consume_task = asyncio.create_task(self._listen_redis())
        except Exception as e:
            logger.error("Failed to start StreamManager", error=str(e), exc_info=True)
            raise

    async def stop(self):
        logger.info("Stopping StreamManager")
        self._running = False
        if self.pubsub:
            try:
                await self.pubsub.punsubscribe("market_data:*")
                await self.pubsub.close()
            except Exception:
                pass
        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
        if self.redis_client:
            await self.redis_client.aclose()
        logger.info("StreamManager stopped")

    async def _listen_redis(self):
        try:
            async for message in self.pubsub.listen():
                if not self._running:
                    break
                if message["type"] == "pmessage":
                    channel = message["channel"].decode("utf-8")
                    symbol = channel.split(":")[-1]
                    data = message["data"]  # Raw bytes

                    queues = list(self.clients.get(symbol, []))
                    for q in queues:
                        try:
                            q.put_nowait(data)
                        except asyncio.QueueFull:
                            pass  # Drop if client is too slow
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Error listening to Redis", error=str(e), exc_info=True)

    def subscribe(self, symbols: str | list[str]) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=1000)
        if isinstance(symbols, str):
            symbols = [symbols]
        for s in symbols:
            self.clients[s].add(q)
        return q

    def unsubscribe(self, symbols: str | list[str], q: asyncio.Queue):
        if isinstance(symbols, str):
            symbols = [symbols]
        for s in symbols:
            if q in self.clients.get(s, set()):
                self.clients[s].remove(q)
                # Cleanup empty sets to avoid memory leaks
                if not self.clients[s]:
                    del self.clients[s]

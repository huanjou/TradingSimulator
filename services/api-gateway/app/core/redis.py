from collections.abc import AsyncGenerator

from redis.asyncio import Redis, from_url


class RedisClient:
    def __init__(self):
        self.client: Redis | None = None

    async def connect(self, url: str) -> None:
        if self.client is None:
            self.client = from_url(url, decode_responses=True)

    async def disconnect(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def get_client(self) -> AsyncGenerator[Redis, None]:
        if self.client is None:
            raise RuntimeError("Redis is not initialized")
        yield self.client


redis_client = RedisClient()


async def get_redis() -> AsyncGenerator[Redis, None]:
    async for client in redis_client.get_client():
        yield client

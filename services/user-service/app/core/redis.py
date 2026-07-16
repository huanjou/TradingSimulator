from collections.abc import AsyncGenerator

from redis.asyncio import Redis, from_url

from app.core.config import settings

# Global redis connection pool
_redis_client: Redis | None = None


async def init_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis():
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()


async def get_redis() -> AsyncGenerator[Redis, None]:
    if _redis_client is None:
        await init_redis()
    yield _redis_client

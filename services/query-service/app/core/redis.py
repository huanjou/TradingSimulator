import logging

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Connection pool
redis_pool = ConnectionPool.from_url(str(settings.REDIS_URL), decode_responses=True)

redis_client = Redis(connection_pool=redis_pool)


async def get_cached_order(order_id: str):
    try:
        data = await redis_client.hgetall(f"order:{order_id}")
        return data if data else None
    except Exception as e:
        logger.error(f"Failed to get cached order {order_id}: {e}")
        return None

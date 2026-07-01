import logging

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Connection pool
redis_pool = ConnectionPool.from_url(str(settings.REDIS_URL), decode_responses=True)

redis_client = Redis(connection_pool=redis_pool)


async def cache_order(order_data: dict):
    """
    Cache order in Redis.
    Key: order:{order_id}
    Also add to user orders list: user:{user_id}:orders (zset or list)
    """
    try:
        order_id = order_data["id"]
        user_id = order_data["user_id"]

        # Save order hash
        await redis_client.hset(f"order:{order_id}", mapping=order_data)

        # Add to user orders list (zset by time, or simply a list)
        await redis_client.sadd(f"user:{user_id}:orders", order_id)

        # Set expiration if needed
        # await redis_client.expire(f"order:{order_id}", 3600)
    except Exception as e:
        logger.error(f"Failed to cache order {order_data.get('id')}: {e}")

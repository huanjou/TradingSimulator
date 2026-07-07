import logging

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


async def get_cached_order(order_id: str):
    """
    Fetches an order from Redis cache.
    """
    try:
        data = await redis_client.hgetall(f"order:{order_id}")
        return data if data else None
    except Exception as e:
        logger.error(f"Failed to get cached order {order_id}: {e}")
        return None

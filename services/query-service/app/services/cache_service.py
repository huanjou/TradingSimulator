import structlog

from app.core.redis import redis_client

logger = structlog.get_logger(__name__)


async def get_cached_order(order_id: str):
    """
    Fetches an order from Redis cache.
    """
    try:
        data = await redis_client.hgetall(f"order:{order_id}")
        return data if data else None
    except Exception as e:
        logger.error(
            "cache_read_failed", order_id=order_id, error=str(e), exc_info=True
        )
        return None

import structlog
from app.core.redis import redis_client

logger = structlog.get_logger(__name__)


async def get_cached_order(order_id: str):
    """
    Fetches an order from Redis cache.
    """
    try:
        data = await redis_client.hgetall(f"order:{order_id}")
        if data:
            for k, v in data.items():
                if v in ("", "None", "null"):
                    data[k] = None
            return data
        return None
    except Exception as e:
        logger.error(
            "cache_read_failed", order_id=order_id, error=str(e), exc_info=True
        )
        return None


async def set_cached_order(order_id: str, order_data: dict, ttl: int = 60):
    """
    Sets an order in Redis cache.
    """
    try:
        data_to_store = {
            k: ("" if v is None else str(v)) for k, v in order_data.items()
        }
        await redis_client.hset(f"order:{order_id}", mapping=data_to_store)
        await redis_client.expire(f"order:{order_id}", ttl)
    except Exception as e:
        logger.error(
            "cache_write_failed", order_id=order_id, error=str(e), exc_info=True
        )

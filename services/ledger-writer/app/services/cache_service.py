import logging

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


async def cache_order(order_data: dict):
    """
    Cache order in Redis.
    Key: order:{order_id}
    Also add to user orders list: user:{user_id}:orders (zset or list)
    """
    try:
        order_id = order_data.get("id") or order_data.get("order_id")
        user_id = order_data.get("user_id")

        if not order_id:
            logger.error("Missing order ID for caching")
            return

        # Save order hash (works for partial updates too)
        await redis_client.hset(f"order:{order_id}", mapping=order_data)

        # Add to user orders list if user_id is present
        if user_id:
            await redis_client.sadd(f"user:{user_id}:orders", order_id)

        # Set expiration if needed
        # await redis_client.expire(f"order:{order_id}", 3600)
    except Exception as e:
        logger.error(f"Failed to cache order {order_data.get('id')}: {e}")

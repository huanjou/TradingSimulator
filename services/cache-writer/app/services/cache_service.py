import logging

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


async def cache_orders_bulk(orders_data: list[dict]):
    """
    Cache a batch of orders in Redis using pipeline.
    """
    try:
        pipeline = redis_client.pipeline(transaction=False)
        for order_data in orders_data:
            order_id = order_data.get("id") or order_data.get("order_id")
            user_id = order_data.get("user_id")

            if not order_id:
                continue

            # Save order hash
            pipeline.hset(f"order:{order_id}", mapping=order_data)

            # Add to user orders list
            if user_id:
                pipeline.sadd(f"user:{user_id}:orders", order_id)

        # Execute all commands in a single network round-trip
        await pipeline.execute()
    except Exception as e:
        logger.error(f"Failed to bulk cache orders: {e}")

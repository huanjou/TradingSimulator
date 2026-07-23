import structlog
from app.core.redis import redis_client

logger = structlog.get_logger(__name__)


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
        logger.error("failed_to_bulk_cache_orders", error=str(e), exc_info=True)
        raise

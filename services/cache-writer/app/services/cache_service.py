import redis.exceptions
import structlog
from app.core.redis import redis_client
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

# Errors indicating Redis is unreachable (as opposed to a bad command/data).
REDIS_ERRORS = (
    redis.exceptions.ConnectionError,
    redis.exceptions.TimeoutError,
    OSError,
)


def _log_redis_retry(retry_state):
    logger.warning(
        "redis_write_retrying",
        attempt=retry_state.attempt_number,
        error=str(retry_state.outcome.exception()),
    )


# Retry transient Redis connectivity failures with exponential backoff; the
# original exception is re-raised after the last attempt so the processor can
# decide how to handle a Redis outage.
redis_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(REDIS_ERRORS),
    before_sleep=_log_redis_retry,
    reraise=True,
)


@redis_retry
async def cache_orders_bulk(orders_data: list[dict]):
    """
    Cache a batch of orders in Redis using pipeline.
    """
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


@redis_retry
async def cache_balances_bulk(balances_data: list[dict]):
    import orjson

    pipeline = redis_client.pipeline(transaction=False)
    for b in balances_data:
        user_id = b.get("user_id")
        currency = b.get("currency")
        if not user_id or not currency:
            continue
        val = orjson.dumps(
            {
                "available": str(b.get("available", "0")),
                "locked": str(b.get("locked", "0")),
            }
        ).decode("utf-8")
        pipeline.hset(f"wallet:{user_id}", currency, val)
    await pipeline.execute()

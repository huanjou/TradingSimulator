"""Redis-backed per-user rate limiting for high-value endpoints.

Unlike the nginx per-IP limits, this counts requests per authenticated user
via a sliding window (sorted set of request timestamps), so a single user
cannot spam orders from one or many IPs.
"""

import time
import uuid

import structlog
from app.core.config import get_settings
from app.core.redis import redis_client
from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)
settings = get_settings()


class UserRateLimiter:
    """Per-user rate limiter using a Redis sliding window."""

    def __init__(
        self,
        redis: Redis | None,
        max_requests: int = 10,
        window_seconds: int = 1,
    ):
        self.redis = redis
        self.max_requests = max_requests
        self.window = window_seconds

    async def check(self, user_id: str, action: str = "order") -> None:
        """Raise HTTP 429 if `user_id` exceeded the limit for `action`."""
        if self.redis is None:
            # Fail open: rate limiting is best-effort protection and must not
            # block the order flow when Redis was never initialized.
            logger.warning("rate_limit_skipped_no_redis", action=action)
            return

        key = f"rate_limit:{action}:{user_id}"
        now = time.time()

        try:
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - self.window)
            # Unique member so concurrent requests with identical timestamps
            # are all counted.
            pipe.zadd(key, {f"{now}:{uuid.uuid4().hex}": now})
            pipe.zcard(key)
            pipe.expire(key, self.window + 1)
            results = await pipe.execute()
        except RedisError as e:
            # Fail open: an unavailable Redis must not take down trading.
            logger.warning("rate_limit_redis_unavailable", error=str(e))
            return

        count = results[2]
        if count > self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: max {self.max_requests} "
                    f"{action}s per {self.window}s"
                ),
            )


def get_order_rate_limiter() -> UserRateLimiter:
    return UserRateLimiter(
        redis=redis_client.client,
        max_requests=settings.ORDER_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=settings.ORDER_RATE_LIMIT_WINDOW_SECONDS,
    )

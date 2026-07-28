from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.rate_limit import UserRateLimiter
from fastapi import HTTPException
from redis.exceptions import RedisError


def _mock_redis(zcard_result: int) -> MagicMock:
    """Builds a mock Redis whose pipeline returns a given zcard count."""
    pipe = MagicMock()
    pipe.execute = AsyncMock(return_value=[0, 1, zcard_result, True])
    redis = MagicMock()
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


async def test_check_allows_under_limit():
    limiter = UserRateLimiter(_mock_redis(zcard_result=5), max_requests=10)
    await limiter.check("user-1", "order")  # Must not raise


async def test_check_rejects_over_limit_with_429():
    limiter = UserRateLimiter(_mock_redis(zcard_result=11), max_requests=10)
    with pytest.raises(HTTPException) as exc_info:
        await limiter.check("user-1", "order")
    assert exc_info.value.status_code == 429


async def test_check_is_per_user_key():
    redis = _mock_redis(zcard_result=1)
    limiter = UserRateLimiter(redis, max_requests=10)
    await limiter.check("user-42", "order")
    pipe = redis.pipeline.return_value
    key = pipe.zremrangebyscore.call_args[0][0]
    assert key == "rate_limit:order:user-42"


async def test_check_fails_open_without_redis():
    limiter = UserRateLimiter(None, max_requests=10)
    await limiter.check("user-1", "order")  # Must not raise


async def test_check_fails_open_on_redis_error():
    redis = _mock_redis(zcard_result=0)
    redis.pipeline.return_value.execute = AsyncMock(side_effect=RedisError("down"))
    limiter = UserRateLimiter(redis, max_requests=10)
    await limiter.check("user-1", "order")  # Must not raise

import time

import redis.asyncio as redis
from fastapi import HTTPException, Request, status

# We will initialize this in main.py
redis_client: redis.Redis = None


class RateLimiter:
    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds

    async def __call__(self, request: Request):
        if not redis_client:
            return  # Skip if redis is not configured

        from app.core.config import get_settings

        if get_settings().ENV == "test":
            return  # Skip in tests

        # Identify client securely
        # Note: Trusting X-Forwarded-For blindly is insecure.
        # In a real production setup, the proxy (like Nginx/Traefik) should set X-Real-IP
        # or we should strip untrusted X-Forwarded-For headers before they reach here.
        # We'll use request.client.host as the primary source of truth.
        ip = request.client.host if request.client else "127.0.0.1"

        key = f"rate_limit:{request.url.path}:{ip}"

        # Leaky bucket / sliding window
        now = time.time()

        try:
            async with redis_client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, now - self.seconds)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, self.seconds)
                results = await pipe.execute()

            request_count = results[2]

            if request_count > self.times:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too Many Requests",
                )
        except redis.RedisError:
            # If Redis is down, fail open (allow request) to prevent complete outage
            pass

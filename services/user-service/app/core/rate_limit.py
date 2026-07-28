"""Redis-backed brute-force protection for authentication endpoints.

Failed login attempts are counted per (email, client-ip) pair. After
``MAX_FAILED_ATTEMPTS`` failures within ``WINDOW_SECONDS`` the identifier is
locked out until the window expires. A successful login clears the counter.
"""

from redis.asyncio import Redis

MAX_FAILED_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60  # 15 minutes


class TooManyAttemptsException(Exception):
    """Raised when an identifier exceeds the allowed number of failed logins."""


def _key(identifier: str) -> str:
    return f"login_attempts:{identifier}"


async def ensure_not_locked(redis: Redis, identifier: str) -> None:
    attempts = await redis.get(_key(identifier))
    if attempts is not None and int(attempts) >= MAX_FAILED_ATTEMPTS:
        raise TooManyAttemptsException(
            "Too many failed login attempts. Please try again later."
        )


async def register_failure(redis: Redis, identifier: str) -> None:
    key = _key(identifier)
    current = await redis.incr(key)
    if current == 1:
        # First failure starts the sliding lockout window.
        await redis.expire(key, WINDOW_SECONDS)


async def reset(redis: Redis, identifier: str) -> None:
    await redis.delete(_key(identifier))

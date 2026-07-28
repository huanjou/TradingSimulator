import logging

from app.core.config import get_settings
from redis.asyncio import ConnectionPool, Redis

settings = get_settings()
logger = logging.getLogger(__name__)

# Connection pool with fail-fast timeouts so a dead Redis never hangs the
# consumer loop indefinitely.
redis_pool = ConnectionPool.from_url(
    str(settings.REDIS_URL),
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
    health_check_interval=10,
)

redis_client = Redis(connection_pool=redis_pool)

import logging

from app.core.config import get_settings
from redis.asyncio import ConnectionPool, Redis

settings = get_settings()
logger = logging.getLogger(__name__)

# Connection pool
redis_pool = ConnectionPool.from_url(str(settings.REDIS_URL), decode_responses=True)

redis_client = Redis(connection_pool=redis_pool)

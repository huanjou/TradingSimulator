import structlog

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)

# Connection pool
redis_pool = ConnectionPool.from_url(str(settings.REDIS_URL), decode_responses=True)

redis_client = Redis(connection_pool=redis_pool)

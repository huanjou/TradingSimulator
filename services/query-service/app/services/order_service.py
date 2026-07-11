import structlog
from opentelemetry import metrics
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.order import OrderEntity
from app.repositories.order import OrderRepository
from app.services.cache_service import get_cached_order

logger = structlog.get_logger(__name__)
meter = metrics.get_meter(__name__)
order_queries_counter = meter.create_counter(
    "order_queries_total",
    description="Total number of order read queries",
)


async def get_order_by_id(db: AsyncSession, order_id: str) -> OrderEntity | None:
    """
    Fetches an order. First checks Redis cache, then fallback to Replica DB.
    """
    order_queries_counter.add(1)
    # 1. Try Cache
    cached_order_dict = await get_cached_order(order_id)
    if cached_order_dict:
        logger.info("cache_hit", order_id=order_id)
        return OrderEntity(**cached_order_dict)

    # 2. Try DB (Read Replica)
    logger.info("cache_miss", order_id=order_id)
    repo = OrderRepository(db)
    order_entity = await repo.get_by_id(order_id)

    return order_entity


async def get_pending_orders(db: AsyncSession) -> list[OrderEntity]:
    repo = OrderRepository(db)
    return await repo.get_pending_orders()

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.order import OrderEntity
from app.repositories.order import OrderRepository
from app.services.cache_service import get_cached_order

logger = logging.getLogger(__name__)


async def get_order_by_id(db: AsyncSession, order_id: str) -> OrderEntity | None:
    """
    Fetches an order. First checks Redis cache, then fallback to Replica DB.
    """
    # 1. Try Cache
    cached_order_dict = await get_cached_order(order_id)
    if cached_order_dict:
        logger.info(f"Cache hit for order {order_id}")
        return OrderEntity(**cached_order_dict)

    # 2. Try DB (Read Replica)
    logger.info(f"Cache miss for order {order_id}, fetching from Replica DB")
    repo = OrderRepository(db)
    order_entity = await repo.get_by_id(order_id)

    return order_entity

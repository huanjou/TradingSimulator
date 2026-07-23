import structlog
from app.domain.order import OrderEntity
from app.repositories.order import OrderRepository
from app.services.cache_service import get_cached_order, set_cached_order
from opentelemetry import metrics

logger = structlog.get_logger(__name__)
meter = metrics.get_meter(__name__)
order_queries_counter = meter.create_counter(
    "order_queries_total",
    description="Total number of order read queries",
)
cache_hits_counter = meter.create_counter(
    "cache_hits_total",
    description="Total number of cache hits",
)
cache_misses_counter = meter.create_counter(
    "cache_misses_total",
    description="Total number of cache misses",
)


async def get_order_by_id(repo: OrderRepository, order_id: str) -> OrderEntity | None:
    """
    Fetches an order. First checks Redis cache, then fallback to Replica DB.
    """
    order_queries_counter.add(1)
    # 1. Try Cache
    cached_order_dict = await get_cached_order(order_id)
    if cached_order_dict:
        cache_hits_counter.add(1)
        logger.info("cache_hit", order_id=order_id)
        return OrderEntity(**cached_order_dict)

    # 2. Try DB (Read Replica)
    cache_misses_counter.add(1)
    logger.info("cache_miss", order_id=order_id)
    order_entity = await repo.get_by_id(order_id)

    if order_entity:
        entity_dict = order_entity.model_dump(mode="json")
        await set_cached_order(order_id, entity_dict, ttl=60)

    return order_entity


async def get_pending_orders(repo: OrderRepository) -> list[OrderEntity]:
    return await repo.get_pending_orders()

import logging

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_cached_order
from app.db.base import *  # This ensures all models are registered
from app.db.session import get_db
from app.models.order import Order

logger = logging.getLogger(__name__)

app = FastAPI(title="Query Service", version="0.1.0")


@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get order by ID.
    First checks Redis cache. If miss, checks Read Replica DB.
    """
    # 1. Try Cache
    cached_order = await get_cached_order(order_id)
    if cached_order:
        logger.info(f"Cache hit for order {order_id}")
        return cached_order

    # 2. Try DB (Read Replica)
    logger.info(f"Cache miss for order {order_id}, fetching from Replica DB")
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "id": str(order.id),
        "user_id": str(order.user_id),
        "symbol": order.symbol,
        "side": order.side.value if hasattr(order.side, "value") else order.side,
        "order_type": order.order_type.value
        if hasattr(order.order_type, "value")
        else order.order_type,
        "quantity": order.quantity,
        "price": order.price,
        "status": order.status.value
        if hasattr(order.status, "value")
        else order.status,
    }

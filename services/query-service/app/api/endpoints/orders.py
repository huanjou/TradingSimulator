import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, get_primary_db
from app.services.order_service import get_order_by_id, get_pending_orders

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/pending")
async def get_all_pending_orders(db: AsyncSession = Depends(get_primary_db)):
    """
    Get all pending orders for state recovery.
    """
    logger.info("fetching_pending_orders")
    orders = await get_pending_orders(db)
    return orders


@router.get("/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get order by ID.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=str(uuid.uuid4()), order_id=order_id, http_method="GET"
    )
    logger.info("http_request_received")

    order = await get_order_by_id(db, order_id)
    if not order:
        logger.warning("order_not_found")
        raise HTTPException(status_code=404, detail="Order not found")

    logger.info("order_fetched")
    return order

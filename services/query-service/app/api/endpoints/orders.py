import structlog

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.session import get_db
from app.services.order_service import get_order_by_id

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get order by ID.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=str(uuid.uuid4()),
        order_id=order_id,
        http_method="GET"
    )
    logger.info("http_request_received")
    
    order = await get_order_by_id(db, order_id)
    if not order:
        logger.warning("order_not_found")
        raise HTTPException(status_code=404, detail="Order not found")

    logger.info("order_fetched")
    return order

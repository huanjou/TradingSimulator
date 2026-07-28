import uuid

import structlog
from app.core.auth import get_current_admin_user, get_token_payload
from app.db.session import get_db, get_primary_db
from app.repositories.order import OrderRepository
from app.services.order_service import get_order_by_id, get_pending_orders
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/pending")
async def get_all_pending_orders(
    db: AsyncSession = Depends(get_primary_db),
    admin_user_id: str = Depends(get_current_admin_user),
):
    """
    Get all pending orders for state recovery.
    Admin only: exposes orders of every user.
    """
    logger.info("fetching_pending_orders", admin_user_id=admin_user_id)
    repo = OrderRepository(db)
    orders = await get_pending_orders(repo)
    return orders


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_token_payload),
):
    """
    Get order by ID. Only the order owner (or an admin) may read it.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=str(uuid.uuid4()), order_id=order_id, http_method="GET"
    )
    logger.info("http_request_received")

    repo = OrderRepository(db)
    order = await get_order_by_id(repo, order_id)
    if not order:
        logger.warning("order_not_found")
        raise HTTPException(status_code=404, detail="Order not found")

    is_admin = token_payload.get("role") == "admin"
    if not is_admin and order.user_id != token_payload["sub"]:
        logger.warning("order_access_denied", owner_id=order.user_id)
        raise HTTPException(
            status_code=403, detail="Not authorized to access this order"
        )

    logger.info("order_fetched")
    return order

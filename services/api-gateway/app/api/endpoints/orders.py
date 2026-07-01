import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.order import OrderCreate, OrderResponse
from app.services.order import order_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Create a new trading order.
    """
    return await order_service.create_order(db=db, order_in=order_in)

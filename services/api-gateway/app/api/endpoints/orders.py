import logging
from typing import Any

from fastapi import APIRouter, status

from app.schemas.order import OrderCreate, OrderResponse
from app.services.order import order_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_order(
    order_in: OrderCreate
) -> Any:
    """
    Create a new trading order.
    Returns 202 Accepted as the order is accepted for processing via Kafka.
    """
    return await order_service.create_order(order_in=order_in)

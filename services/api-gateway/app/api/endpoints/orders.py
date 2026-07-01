import logging
from typing import Any

from fastapi import APIRouter, status

from app.schemas.order import OrderCreate, OrderResponse
from app.services.order import order_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_order(order_in: OrderCreate) -> Any:
    """
    Create a new trading order.
    Returns 202 Accepted as the order is accepted for processing via Kafka.
    """
    return await order_service.create_order(order_in=order_in)


import os

import httpx
from fastapi import HTTPException

QUERY_SERVICE_URL = os.getenv("QUERY_SERVICE_URL", "http://query-service:8000")


@router.get("/{order_id}")
async def get_order(order_id: str) -> Any:
    """
    Get order by ID by calling the internal query-service.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{QUERY_SERVICE_URL}/api/v1/orders/{order_id}")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Order not found")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Error calling query-service: {e}")
            raise HTTPException(status_code=503, detail="Query service unavailable")

import logging
from typing import Any

from fastapi import APIRouter, status

from app.schemas.order import OrderCreate, OrderResponse
from app.services.order import order_service

from opentelemetry import metrics

router = APIRouter()
logger = logging.getLogger(__name__)

meter = metrics.get_meter(__name__)
orders_submitted_counter = meter.create_counter(
    "orders_submitted_total",
    description="Total number of trading orders submitted",
)

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_order(order_in: OrderCreate) -> Any:
    """
    Create a new trading order.
    Returns 202 Accepted as the order is accepted for processing via Kafka.
    """
    orders_submitted_counter.add(1, {"symbol": order_in.symbol, "side": order_in.side.value})
    return await order_service.create_order(order_in=order_in)


import os
import grpc
from fastapi import HTTPException
from app.grpc_stubs import orders_pb2, orders_pb2_grpc

QUERY_SERVICE_GRPC_URL = os.getenv("QUERY_SERVICE_GRPC_URL", "query-service:50051")


@router.get("/{order_id}")
async def get_order(order_id: str) -> Any:
    """
    Get order by ID by calling the internal query-service via gRPC.
    """
    try:
        async with grpc.aio.insecure_channel(QUERY_SERVICE_GRPC_URL) as channel:
            stub = orders_pb2_grpc.OrderQueryServiceStub(channel)
            request = orders_pb2.GetOrderRequest(order_id=order_id)
            response = await stub.GetOrder(request)
            
            # Since gRPC returns default values for missing strings, we check if ID is empty
            if not response.id:
                raise HTTPException(status_code=404, detail="Order not found")
                
            return {
                "id": response.id,
                "user_id": response.user_id,
                "symbol": response.symbol,
                "side": response.side,
                "order_type": response.order_type,
                "quantity": response.quantity,
                "price": response.price,
                "status": response.status,
                "created_at": response.created_at,
                "updated_at": response.updated_at,
            }
    except grpc.aio.AioRpcError as e:
        logger.error(f"gRPC error calling query-service: {e.details()}")
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=503, detail="Query service unavailable")

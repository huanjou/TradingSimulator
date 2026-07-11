import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from opentelemetry import metrics

from app.schemas.order import OrderCreate, OrderResponse
from app.services.order import order_service

router = APIRouter()
logger = logging.getLogger(__name__)

meter = metrics.get_meter(__name__)
orders_submitted_counter = meter.create_counter(
    "orders_submitted_total",
    description="Total number of trading orders submitted",
)

from fastapi import Request

from app.api.rate_limiter import RateLimiter


async def ip_identifier(request: Request):
    """
    Use X-Forwarded-For header to identify clients if behind a proxy.
    This allows our load testing tool (K6) to simulate multiple IP addresses.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter(times=10, seconds=1))],
)
async def create_order(order_in: OrderCreate) -> Any:
    """
    Create a new trading order.
    Returns 202 Accepted as the order is accepted for processing via Kafka.
    """
    orders_submitted_counter.add(
        1, {"symbol": order_in.symbol, "side": order_in.side.value}
    )
    return await order_service.create_order(order_in=order_in)


import os

import grpc
from fastapi import Depends, HTTPException

from app.grpc_stubs import orders_pb2, orders_pb2_grpc

QUERY_SERVICE_GRPC_URL = os.getenv("QUERY_SERVICE_GRPC_URL", "query-service:50051")


@router.get(
    "/{order_id}",
    dependencies=[Depends(RateLimiter(times=50, seconds=1))],
)
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


@router.get(
    "/{order_id}/trades",
    dependencies=[Depends(RateLimiter(times=50, seconds=1))],
)
async def get_order_trades(order_id: str) -> Any:
    """
    Get trades for an order by calling the internal query-service via gRPC.
    """
    try:
        async with grpc.aio.insecure_channel(QUERY_SERVICE_GRPC_URL) as channel:
            stub = orders_pb2_grpc.OrderQueryServiceStub(channel)
            request = orders_pb2.GetTradesRequest(order_id=order_id)
            response = await stub.GetTrades(request)

            return [
                {
                    "id": trade.id,
                    "order_id": trade.order_id,
                    "symbol": trade.symbol,
                    "price": trade.price,
                    "quantity": trade.quantity,
                    "timestamp": trade.timestamp,
                }
                for trade in response.trades
            ]
    except grpc.aio.AioRpcError as e:
        logger.error(f"gRPC error calling query-service GetTrades: {e.details()}")
        raise HTTPException(status_code=503, detail="Query service unavailable")

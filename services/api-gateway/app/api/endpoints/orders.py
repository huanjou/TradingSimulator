import logging
from typing import Any

from app.api.deps import get_current_user_id
from app.api.rate_limiter import RateLimiter
from app.schemas.order import OrderCreate, OrderResponse
from app.services.order import order_service
from app.services.order_query import order_query_service
from fastapi import APIRouter, Depends, Request, status
from opentelemetry import metrics

router = APIRouter()
logger = logging.getLogger(__name__)

meter = metrics.get_meter(__name__)
orders_submitted_counter = meter.create_counter(
    "orders_submitted_total",
    description="Total number of trading orders submitted",
)


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter(times=10, seconds=1))],
)
async def create_order(
    order_in: OrderCreate, current_user_id: str = Depends(get_current_user_id)
) -> Any:
    """
    Create a new trading order.
    Returns 202 Accepted as the order is accepted for processing via Kafka.
    """
    orders_submitted_counter.add(
        1, {"symbol": order_in.symbol, "side": order_in.side.value}
    )
    return await order_service.create_order(user_id=current_user_id, order_in=order_in)


@router.get(
    "/{order_id}",
    dependencies=[Depends(RateLimiter(times=50, seconds=1))],
)
async def get_order(
    order_id: str, request: Request, current_user_id: str = Depends(get_current_user_id)
) -> Any:
    """
    Get order by ID by calling the internal query-service via gRPC.
    """
    return await order_query_service.get_order(
        channel=request.app.state.grpc_channel,
        order_id=order_id,
        current_user_id=current_user_id,
    )


@router.get(
    "/{order_id}/trades",
    dependencies=[Depends(RateLimiter(times=50, seconds=1))],
)
async def get_order_trades(
    order_id: str, request: Request, current_user_id: str = Depends(get_current_user_id)
) -> Any:
    """
    Get trades for an order by calling the internal query-service via gRPC.
    """
    return await order_query_service.get_order_trades(
        channel=request.app.state.grpc_channel,
        order_id=order_id,
        current_user_id=current_user_id,
    )


@router.get(
    "/user/{user_id}",
    dependencies=[Depends(RateLimiter(times=50, seconds=1))],
)
async def get_orders_by_user(
    user_id: str,
    request: Request,
    limit: int = 50,
    offset: int = 0,
    current_user_id: str = Depends(get_current_user_id),
) -> Any:
    """
    Get orders for a specific user by calling the internal query-service via gRPC.
    """
    return await order_query_service.get_orders_by_user(
        channel=request.app.state.grpc_channel,
        user_id=user_id,
        current_user_id=current_user_id,
        limit=limit,
        offset=offset,
    )

import logging
from datetime import datetime, timezone
from typing import Any

import grpc
from app.api.exceptions import (
    OrderNotFoundException,
    OrderQueryServiceUnavailableException,
    UnauthorizedOrderAccessException,
)
from app.grpc_stubs import orders_pb2, orders_pb2_grpc

logger = logging.getLogger(__name__)


class OrderQueryService:
    @staticmethod
    async def get_order(
        channel: grpc.aio.Channel, order_id: str, current_user_id: str
    ) -> dict[str, Any]:
        try:
            stub = orders_pb2_grpc.OrderQueryServiceStub(channel)
            req = orders_pb2.GetOrderRequest(order_id=order_id)
            response = await stub.GetOrder(req)

            if not response.id:
                raise OrderNotFoundException("Order not found")

            if response.user_id != current_user_id:
                raise UnauthorizedOrderAccessException(
                    "Not authorized to access this order"
                )

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
                "average_fill_price": response.average_fill_price
                if response.HasField("average_fill_price")
                else None,
            }
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC error calling query-service: {e.details()}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise OrderNotFoundException("Order not found") from e
            raise OrderQueryServiceUnavailableException(
                "Query service unavailable"
            ) from e

    @staticmethod
    async def get_order_trades(
        channel: grpc.aio.Channel, order_id: str, current_user_id: str
    ) -> list[dict[str, Any]]:
        try:
            stub = orders_pb2_grpc.OrderQueryServiceStub(channel)

            # IDOR Fix: Verify order ownership first
            order_req = orders_pb2.GetOrderRequest(order_id=order_id)
            order_res = await stub.GetOrder(order_req)
            if not order_res.id:
                raise OrderNotFoundException("Order not found")
            if order_res.user_id != current_user_id:
                raise UnauthorizedOrderAccessException("Not authorized")

            req = orders_pb2.GetTradesRequest(order_id=order_id)
            response = await stub.GetTrades(req)

            return [
                {
                    "id": trade.id,
                    "order_id": trade.order_id,
                    "symbol": trade.symbol,
                    "price": trade.price,
                    "quantity": trade.quantity,
                    "timestamp": datetime.fromtimestamp(
                        trade.timestamp, tz=timezone.utc
                    ).isoformat(),
                }
                for trade in response.trades
            ]
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC error calling query-service GetTrades: {e.details()}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise OrderNotFoundException("Order not found") from e
            raise OrderQueryServiceUnavailableException(
                "Query service unavailable"
            ) from e

    @staticmethod
    async def get_orders_by_user(
        channel: grpc.aio.Channel,
        user_id: str,
        current_user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if user_id != "me" and user_id != current_user_id:
            raise UnauthorizedOrderAccessException(
                "Not authorized to access these orders"
            )

        target_user_id = current_user_id if user_id == "me" else user_id

        try:
            stub = orders_pb2_grpc.OrderQueryServiceStub(channel)
            req = orders_pb2.GetOrdersByUserRequest(
                user_id=target_user_id, limit=limit, offset=offset
            )
            response = await stub.GetOrdersByUser(req)

            return [
                {
                    "id": order.id,
                    "user_id": order.user_id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "order_type": order.order_type,
                    "quantity": order.quantity,
                    "price": order.price,
                    "status": order.status,
                    "created_at": order.created_at,
                    "updated_at": order.updated_at,
                    "average_fill_price": order.average_fill_price
                    if order.HasField("average_fill_price")
                    else None,
                }
                for order in response.orders
            ]
        except grpc.aio.AioRpcError as e:
            logger.error(
                f"gRPC error calling query-service GetOrdersByUser: {e.details()}"
            )
            raise OrderQueryServiceUnavailableException(
                "Query service unavailable"
            ) from e

    @staticmethod
    async def get_trades_by_user(
        channel: grpc.aio.Channel,
        user_id: str,
        current_user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if user_id != "me" and user_id != current_user_id:
            raise UnauthorizedOrderAccessException(
                "Not authorized to access these trades"
            )

        target_user_id = current_user_id if user_id == "me" else user_id

        try:
            stub = orders_pb2_grpc.OrderQueryServiceStub(channel)
            req = orders_pb2.GetTradesByUserRequest(
                user_id=target_user_id, limit=limit, offset=offset
            )
            response = await stub.GetTradesByUser(req)

            return [
                {
                    "id": trade.id,
                    "order_id": trade.order_id,
                    "symbol": trade.symbol,
                    "price": trade.price,
                    "quantity": trade.quantity,
                    "timestamp": datetime.fromtimestamp(
                        trade.timestamp, tz=timezone.utc
                    ).isoformat(),
                }
                for trade in response.trades
            ]
        except grpc.aio.AioRpcError as e:
            logger.error(
                f"gRPC error calling query-service GetTradesByUser: {e.details()}"
            )
            raise OrderQueryServiceUnavailableException(
                "Query service unavailable"
            ) from e


order_query_service = OrderQueryService()

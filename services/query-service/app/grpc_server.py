import uuid

import grpc
import structlog

from app.db.session import AsyncSessionLocal
from app.grpc_stubs import orders_pb2, orders_pb2_grpc
from app.services.order_service import get_order_by_id

logger = structlog.get_logger(__name__)


class OrderQueryServiceServicer(orders_pb2_grpc.OrderQueryServiceServicer):
    async def GetOrder(
        self, request: orders_pb2.GetOrderRequest, context: grpc.aio.ServicerContext
    ) -> orders_pb2.OrderResponse:
        order_id = request.order_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()), order_id=order_id, grpc_method="GetOrder"
        )
        logger.info("grpc_request_received")

        try:
            async with AsyncSessionLocal() as db_session:
                order = await get_order_by_id(db_session, order_id)
                if not order:
                    logger.warning("order_not_found")
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Order {order_id} not found")
                    return orders_pb2.OrderResponse()

                logger.info("order_fetched")
                return orders_pb2.OrderResponse(
                    id=str(order.id),
                    user_id=str(order.user_id),
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    price=order.price,
                    status=order.status,
                    created_at=order.created_at.isoformat()
                    if getattr(order, "created_at", None)
                    else "",
                    updated_at=order.updated_at.isoformat()
                    if getattr(order, "updated_at", None)
                    else "",
                )
        except Exception as e:
            logger.error("grpc_request_failed", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return orders_pb2.OrderResponse()

    async def GetTrades(
        self, request: orders_pb2.GetTradesRequest, context: grpc.aio.ServicerContext
    ) -> orders_pb2.GetTradesResponse:
        order_id = request.order_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()), order_id=order_id, grpc_method="GetTrades"
        )
        logger.info("grpc_get_trades_request_received")

        try:
            from app.repositories.trade import trade_repo

            async with AsyncSessionLocal() as db_session:
                trades = await trade_repo.get_by_order_id(db_session, order_id)
                logger.info("trades_fetched", count=len(trades))
                return orders_pb2.GetTradesResponse(
                    trades=[
                        orders_pb2.Trade(
                            id=str(t.id),
                            order_id=str(t.order_id),
                            symbol=t.symbol,
                            price=t.price,
                            quantity=t.quantity,
                            timestamp=t.timestamp,
                        )
                        for t in trades
                    ]
                )
        except Exception as e:
            logger.error("grpc_get_trades_failed", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return orders_pb2.GetTradesResponse()

    async def GetOrdersByUser(
        self,
        request: orders_pb2.GetOrdersByUserRequest,
        context: grpc.aio.ServicerContext,
    ) -> orders_pb2.GetOrdersByUserResponse:
        user_id = request.user_id
        limit = request.limit if request.limit > 0 else 50
        offset = request.offset if request.offset >= 0 else 0

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()), user_id=user_id, grpc_method="GetOrdersByUser"
        )
        logger.info("grpc_get_orders_by_user_request_received")

        try:
            from app.repositories.order import OrderRepository

            async with AsyncSessionLocal() as db_session:
                repo = OrderRepository(db_session)
                orders = await repo.get_by_user_id(user_id, limit, offset)

                logger.info("orders_fetched", count=len(orders))
                return orders_pb2.GetOrdersByUserResponse(
                    orders=[
                        orders_pb2.OrderResponse(
                            id=str(o.id),
                            user_id=str(o.user_id),
                            symbol=o.symbol,
                            side=o.side,
                            order_type=o.order_type,
                            quantity=o.quantity,
                            price=o.price,
                            status=o.status,
                            created_at=o.created_at.isoformat()
                            if getattr(o, "created_at", None)
                            else "",
                            updated_at=o.updated_at.isoformat()
                            if getattr(o, "updated_at", None)
                            else "",
                        )
                        for o in orders
                    ]
                )
        except Exception as e:
            logger.error("grpc_get_orders_by_user_failed", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return orders_pb2.GetOrdersByUserResponse()


async def serve_grpc():
    server = grpc.aio.server()
    orders_pb2_grpc.add_OrderQueryServiceServicer_to_server(
        OrderQueryServiceServicer(), server
    )
    port = "[::]:50051"
    server.add_insecure_port(port)
    logger.info("grpc_server_started", port=port)
    await server.start()
    await server.wait_for_termination()

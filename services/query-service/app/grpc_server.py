import structlog

import grpc
import uuid

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
            request_id=str(uuid.uuid4()),
            order_id=order_id,
            grpc_method="GetOrder"
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
                    created_at=getattr(order, "created_at").isoformat() if getattr(order, "created_at", None) else "",
                    updated_at=getattr(order, "updated_at").isoformat() if getattr(order, "updated_at", None) else "",
                )
        except Exception as e:
            logger.error("grpc_request_failed", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return orders_pb2.OrderResponse()


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

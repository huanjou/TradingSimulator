import logging

import grpc

from app.db.session import AsyncSessionLocal
from app.grpc_stubs import orders_pb2, orders_pb2_grpc
from app.services.order_service import get_order_by_id

logger = logging.getLogger(__name__)


class OrderQueryServiceServicer(orders_pb2_grpc.OrderQueryServiceServicer):
    async def GetOrder(
        self, request: orders_pb2.GetOrderRequest, context: grpc.aio.ServicerContext
    ) -> orders_pb2.OrderResponse:
        order_id = request.order_id
        try:
            async with AsyncSessionLocal() as db_session:
                order = await get_order_by_id(db_session, order_id)
                if not order:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Order {order_id} not found")
                    return orders_pb2.OrderResponse()

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
            logger.exception(f"Error fetching order in gRPC: {e}")
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
    logger.info(f"Starting gRPC server on {port}")
    await server.start()
    await server.wait_for_termination()

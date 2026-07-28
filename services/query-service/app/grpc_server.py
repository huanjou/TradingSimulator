import contextvars
import uuid
from collections.abc import Awaitable, Callable

import grpc
import structlog
from app.core.auth import decode_token
from app.db.session import AsyncSessionLocal
from app.grpc_stubs import orders_pb2, orders_pb2_grpc
from app.repositories.order import OrderRepository
from app.repositories.trade import trade_repo
from app.services.order_service import get_order_by_id
from jose import JWTError

logger = structlog.get_logger(__name__)

# Payload of the authenticated JWT, bound per-RPC by JwtAuthInterceptor.
_auth_payload_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "grpc_auth_payload"
)


def get_authenticated_user() -> tuple[str, bool]:
    """Returns (user_id, is_admin) for the current RPC."""
    payload = _auth_payload_ctx.get({})
    return payload.get("sub", ""), payload.get("role") == "admin"


class JwtAuthInterceptor(grpc.aio.ServerInterceptor):
    """
    Validates the JWT passed in the 'authorization' metadata key
    ("Bearer <token>") and binds its payload to the RPC context.
    Rejects the call with UNAUTHENTICATED when the token is missing/invalid.
    """

    async def intercept_service(
        self,
        continuation: Callable[
            [grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]
        ],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        metadata = dict(handler_call_details.invocation_metadata or ())
        token = metadata.get("authorization", "")
        if token.startswith("Bearer "):
            token = token[len("Bearer ") :]

        try:
            if not token:
                raise JWTError("Missing token")
            payload = decode_token(token)
            if not payload.get("sub"):
                raise JWTError("Missing subject claim")
        except JWTError as e:
            logger.warning(
                "grpc_auth_failed",
                grpc_method=handler_call_details.method,
                error=str(e),
            )
            return self._unauthenticated_handler()

        handler = await continuation(handler_call_details)
        return self._with_auth_payload(handler, payload)

    @staticmethod
    def _unauthenticated_handler() -> grpc.RpcMethodHandler:
        async def abort(request, context):
            await context.abort(
                grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing token"
            )

        return grpc.unary_unary_rpc_method_handler(abort)

    @staticmethod
    def _with_auth_payload(
        handler: grpc.RpcMethodHandler | None, payload: dict
    ) -> grpc.RpcMethodHandler | None:
        # All OrderQueryService RPCs are unary-unary.
        if handler is None or handler.unary_unary is None:
            return handler

        inner = handler.unary_unary

        async def behavior(request, context):
            ctx_token = _auth_payload_ctx.set(payload)
            try:
                return await inner(request, context)
            finally:
                _auth_payload_ctx.reset(ctx_token)

        return grpc.unary_unary_rpc_method_handler(
            behavior,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )


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
                repo = OrderRepository(db_session)
                order = await get_order_by_id(repo, order_id)
                if not order:
                    logger.warning("order_not_found")
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Order {order_id} not found")
                    return orders_pb2.OrderResponse()

                auth_user_id, is_admin = get_authenticated_user()
                if not is_admin and order.user_id != auth_user_id:
                    logger.warning("order_access_denied", owner_id=order.user_id)
                    context.set_code(grpc.StatusCode.PERMISSION_DENIED)
                    context.set_details("Not authorized to access this order")
                    return orders_pb2.OrderResponse()

                logger.info("order_fetched")
                return orders_pb2.OrderResponse(
                    id=str(order.id),
                    user_id=str(order.user_id),
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    price=order.price if order.price is not None else 0.0,
                    status=order.status,
                    created_at=order.created_at.isoformat() if order.created_at else "",
                    updated_at=order.updated_at.isoformat() if order.updated_at else "",
                    average_fill_price=order.average_fill_price
                    if order.average_fill_price is not None
                    else 0.0,
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
        limit = request.limit if request.limit > 0 else 50
        offset = request.offset if request.offset >= 0 else 0

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()), order_id=order_id, grpc_method="GetTrades"
        )
        logger.info("grpc_get_trades_request_received")

        try:
            async with AsyncSessionLocal() as db_session:
                order = await get_order_by_id(OrderRepository(db_session), order_id)
                if not order:
                    logger.warning("order_not_found")
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Order {order_id} not found")
                    return orders_pb2.GetTradesResponse()

                auth_user_id, is_admin = get_authenticated_user()
                if not is_admin and order.user_id != auth_user_id:
                    logger.warning("trades_access_denied", owner_id=order.user_id)
                    context.set_code(grpc.StatusCode.PERMISSION_DENIED)
                    context.set_details("Not authorized to access these trades")
                    return orders_pb2.GetTradesResponse()

                trades = await trade_repo.get_by_order_id(
                    db_session,
                    order_id,
                    limit,
                    offset,
                )
                logger.info("trades_fetched", count=len(trades))
                return orders_pb2.GetTradesResponse(
                    trades=[
                        orders_pb2.Trade(
                            id=str(t.id),
                            order_id=str(t.order_id),
                            symbol=t.symbol,
                            price=t.price,
                            quantity=t.quantity,
                            timestamp=float(t.timestamp)
                            if t.timestamp is not None
                            else 0.0,
                        )
                        for t in trades
                    ]
                )
        except Exception as e:
            logger.error("get_trades_error", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal server error")
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

        auth_user_id, is_admin = get_authenticated_user()
        if not is_admin and user_id != auth_user_id:
            logger.warning("orders_by_user_access_denied", auth_user_id=auth_user_id)
            context.set_code(grpc.StatusCode.PERMISSION_DENIED)
            context.set_details("Not authorized to access these orders")
            return orders_pb2.GetOrdersByUserResponse()

        try:
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
                            price=o.price if o.price is not None else 0.0,
                            status=o.status,
                            created_at=o.created_at.isoformat() if o.created_at else "",
                            updated_at=o.updated_at.isoformat() if o.updated_at else "",
                            average_fill_price=o.average_fill_price
                            if o.average_fill_price is not None
                            else 0.0,
                        )
                        for o in orders
                    ]
                )
        except Exception as e:
            logger.error("grpc_get_orders_by_user_failed", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return orders_pb2.GetOrdersByUserResponse()

    async def GetTradesByUser(
        self,
        request: orders_pb2.GetTradesByUserRequest,
        context: grpc.aio.ServicerContext,
    ) -> orders_pb2.GetTradesResponse:
        user_id = request.user_id
        limit = request.limit if request.limit > 0 else 50
        offset = request.offset if request.offset >= 0 else 0

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()), user_id=user_id, grpc_method="GetTradesByUser"
        )
        logger.info("grpc_get_trades_by_user_request_received")

        auth_user_id, is_admin = get_authenticated_user()
        if not is_admin and user_id != auth_user_id:
            logger.warning("trades_by_user_access_denied", auth_user_id=auth_user_id)
            context.set_code(grpc.StatusCode.PERMISSION_DENIED)
            context.set_details("Not authorized to access these trades")
            return orders_pb2.GetTradesResponse()

        try:
            async with AsyncSessionLocal() as db_session:
                trades = await trade_repo.get_by_user_id(
                    db_session,
                    user_id,
                    limit,
                    offset,
                )
                logger.info("trades_by_user_fetched", count=len(trades))
                return orders_pb2.GetTradesResponse(
                    trades=[
                        orders_pb2.Trade(
                            id=str(t.id),
                            order_id=str(t.order_id),
                            symbol=t.symbol,
                            price=t.price,
                            quantity=t.quantity,
                            timestamp=float(t.timestamp)
                            if t.timestamp is not None
                            else 0.0,
                        )
                        for t in trades
                    ]
                )
        except Exception as e:
            logger.error("get_trades_by_user_error", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal server error")
            return orders_pb2.GetTradesResponse()


async def serve_grpc():
    server = grpc.aio.server(interceptors=[JwtAuthInterceptor()])
    orders_pb2_grpc.add_OrderQueryServiceServicer_to_server(
        OrderQueryServiceServicer(), server
    )
    port = "[::]:50051"
    server.add_insecure_port(port)
    logger.info("grpc_server_started", port=port)
    await server.start()
    return server

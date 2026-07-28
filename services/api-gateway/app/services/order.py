import logging
import uuid

from app.api.exceptions import OrderSubmissionFailedException, OrderValidationException
from app.core.kafka import kafka_client
from app.domain.order import OrderEntity
from app.schemas.order import OrderCreate, OrderStatusChoice

logger = logging.getLogger(__name__)


class OrderService:
    @staticmethod
    async def create_order(user_id: str, order_in: OrderCreate) -> OrderEntity:
        try:
            # 1. Map DTO to pure Domain Entity (Status will be PENDING by default)
            domain_order = OrderEntity(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                symbol=order_in.symbol,
                side=order_in.side,
                order_type=order_in.order_type,
                quantity=order_in.quantity,
                price=order_in.price,
                status=OrderStatusChoice.PENDING,
            )

            # 2. Publish order event directly to Kafka (Fire-and-forget)
            await kafka_client.send_event(
                topic="orders",
                key=domain_order.symbol.encode("utf-8"),
                value={
                    "id": str(domain_order.id),
                    "user_id": str(domain_order.user_id),
                    "symbol": domain_order.symbol,
                    "side": domain_order.side.value,
                    "order_type": domain_order.order_type.value,
                    # Money is sent as a string to preserve exact precision
                    # end-to-end (orjson cannot serialize Decimal, and floats
                    # would reintroduce rounding drift).
                    "quantity": str(domain_order.quantity),
                    "price": (
                        str(domain_order.price)
                        if domain_order.price is not None
                        else None
                    ),
                    "status": domain_order.status.value,
                },
            )

            return domain_order
        except ValueError as ve:
            # Domain invariant violation
            logger.warning(f"Domain validation error: {ve}")
            raise OrderValidationException(str(ve)) from ve
        except Exception as e:
            logger.error(f"Error creating order in service: {e}")
            raise OrderSubmissionFailedException(
                f"Failed to submit order: {str(e)}"
            ) from e


order_service = OrderService()

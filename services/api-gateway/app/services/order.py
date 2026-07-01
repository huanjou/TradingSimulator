import logging
import uuid
from fastapi import HTTPException, status

from app.schemas.order import OrderCreate
from app.domain.order import OrderEntity
from app.core.kafka import kafka_client
from app.models.order import OrderStatusChoice

logger = logging.getLogger(__name__)

class OrderService:
    @staticmethod
    async def create_order(order_in: OrderCreate) -> OrderEntity:
        try:
            # 1. Map DTO to pure Domain Entity (Status will be PENDING by default)
            domain_order = OrderEntity(
                id=uuid.uuid4(),
                user_id=order_in.user_id,
                symbol=order_in.symbol,
                side=order_in.side,
                order_type=order_in.order_type,
                quantity=order_in.quantity,
                price=order_in.price,
                status=OrderStatusChoice.PENDING
            )
            
            # 2. Publish order event directly to Kafka (Fire-and-forget)
            await kafka_client.send_event(
                topic="orders",
                value={
                    "id": str(domain_order.id),
                    "user_id": str(domain_order.user_id),
                    "symbol": domain_order.symbol,
                    "side": domain_order.side.value,
                    "type": domain_order.order_type.value,
                    "quantity": domain_order.quantity,
                    "price": domain_order.price,
                    "status": domain_order.status.value,
                }
            )
            
            return domain_order
        except ValueError as ve:
            # Domain invariant violation
            logger.warning(f"Domain validation error: {ve}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )
        except Exception as e:
            logger.error(f"Error creating order in service: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order"
            )

order_service = OrderService()

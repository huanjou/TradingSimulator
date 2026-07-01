import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.schemas.order import OrderCreate
from app.repositories.order import order_repo
from app.domain.order import OrderEntity
from app.core.kafka import kafka_client
from app.models.order import OrderStatusChoice

logger = logging.getLogger(__name__)

class OrderService:
    @staticmethod
    async def create_order(db: AsyncSession, order_in: OrderCreate) -> OrderEntity:
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
            
            # 2. Save to database using Repository
            saved_order = await order_repo.create(db, obj_in=domain_order)
            
            # 3. Publish order event to Kafka
            await kafka_client.send_event(
                topic="orders",
                value={
                    "id": str(saved_order.id),
                    "user_id": str(saved_order.user_id),
                    "symbol": saved_order.symbol,
                    "side": saved_order.side.value,
                    "order_type": saved_order.order_type.value,
                    "quantity": saved_order.quantity,
                    "price": saved_order.price,
                    "status": saved_order.status.value,
                }
            )
            
            return saved_order
        except ValueError as ve:
            # Domain invariant violation
            logger.warning(f"Domain validation error: {ve}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )
        except Exception as e:
            logger.error(f"Error creating order in service: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order"
            )

order_service = OrderService()

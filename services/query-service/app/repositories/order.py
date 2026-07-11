from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.order import OrderEntity
from app.models.order import Order


class OrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, order_id: str) -> OrderEntity | None:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order_model = result.scalar_one_or_none()

        if not order_model:
            return None

        return OrderEntity(
            id=str(order_model.id),
            user_id=str(order_model.user_id),
            symbol=order_model.symbol,
            side=order_model.side.value
            if hasattr(order_model.side, "value")
            else order_model.side,
            order_type=order_model.order_type.value
            if hasattr(order_model.order_type, "value")
            else order_model.order_type,
            quantity=order_model.quantity,
            price=order_model.price,
            status=order_model.status.value
            if hasattr(order_model.status, "value")
            else order_model.status,
        )

    async def get_pending_orders(self) -> list[OrderEntity]:
        result = await self.db.execute(select(Order).where(Order.status == "PENDING"))
        order_models = result.scalars().all()

        return [
            OrderEntity(
                id=str(order_model.id),
                user_id=str(order_model.user_id),
                symbol=order_model.symbol,
                side=order_model.side.value
                if hasattr(order_model.side, "value")
                else order_model.side,
                order_type=order_model.order_type.value
                if hasattr(order_model.order_type, "value")
                else order_model.order_type,
                quantity=order_model.quantity,
                price=order_model.price,
                status=order_model.status.value
                if hasattr(order_model.status, "value")
                else order_model.status,
            )
            for order_model in order_models
        ]

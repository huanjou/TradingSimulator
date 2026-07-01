from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.order import OrderEntity
from app.models.order import Order as DbOrder
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[DbOrder]):
    def _to_domain(self, db_obj: DbOrder) -> OrderEntity:
        return OrderEntity(
            id=db_obj.id,
            user_id=db_obj.user_id,
            symbol=db_obj.symbol,
            side=db_obj.side,
            order_type=db_obj.order_type,
            quantity=db_obj.quantity,
            price=db_obj.price,
            status=db_obj.status,
            created_at=db_obj.created_at,
            updated_at=db_obj.updated_at,
        )

    async def create(self, db: AsyncSession, *, obj_in: OrderEntity) -> OrderEntity:
        # Convert Domain Entity to DB Model
        db_obj = self.model(
            id=obj_in.id,
            user_id=obj_in.user_id,
            symbol=obj_in.symbol,
            side=obj_in.side,
            order_type=obj_in.order_type,
            quantity=obj_in.quantity,
            price=obj_in.price,
            status=obj_in.status,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)

        # Convert back to Domain Entity
        return self._to_domain(db_obj)


order_repo = OrderRepository(DbOrder)

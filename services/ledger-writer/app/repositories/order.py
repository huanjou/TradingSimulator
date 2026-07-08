from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.order import OrderEntity
from app.models.order import Order as DbOrder
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[DbOrder]):
    def _to_domain(self, db_obj: DbOrder) -> OrderEntity:
        return OrderEntity(
            id=str(db_obj.id),
            user_id=str(db_obj.user_id),
            symbol=db_obj.symbol,
            side=db_obj.side.value if hasattr(db_obj.side, "value") else db_obj.side,
            order_type=db_obj.order_type.value
            if hasattr(db_obj.order_type, "value")
            else db_obj.order_type,
            quantity=db_obj.quantity,
            filled_quantity=db_obj.filled_quantity,
            price=db_obj.price,
            status=db_obj.status.value
            if hasattr(db_obj.status, "value")
            else db_obj.status,
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
            filled_quantity=obj_in.filled_quantity,
            price=obj_in.price,
            status=obj_in.status,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)

        return self._to_domain(db_obj)

    async def upsert(self, db: AsyncSession, *, obj_in: OrderEntity) -> None:
        """
        Upsert an order (Insert, or Update status/price if exists).
        """
        stmt = (
            insert(DbOrder)
            .values(
                id=obj_in.id,
                user_id=obj_in.user_id,
                symbol=obj_in.symbol,
                side=obj_in.side,
                order_type=obj_in.order_type,
                quantity=obj_in.quantity,
                filled_quantity=obj_in.filled_quantity,
                price=obj_in.price,
                status=obj_in.status,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_=dict(
                    status=obj_in.status,
                    filled_quantity=obj_in.filled_quantity,
                ),
            )
        )
        await db.execute(stmt)

    async def update_status(self, db: AsyncSession, order_id: str, status: str, filled_quantity: float) -> None:
        from sqlalchemy import update
        stmt = (
            update(DbOrder)
            .where(DbOrder.id == order_id)
            .values(status=status, filled_quantity=filled_quantity)
        )
        await db.execute(stmt)


order_repo = OrderRepository(DbOrder)

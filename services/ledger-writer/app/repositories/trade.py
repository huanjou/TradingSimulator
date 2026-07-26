from app.domain.trade import TradeEntity
from app.models.trade import Trade as DbTrade
from app.repositories.base import BaseRepository
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession


class TradeRepository(BaseRepository[DbTrade]):
    def _to_domain(self, db_obj: DbTrade) -> TradeEntity:
        return TradeEntity(
            id=str(db_obj.id),
            order_id=str(db_obj.order_id),
            symbol=db_obj.symbol,
            price=db_obj.price,
            quantity=db_obj.quantity,
            timestamp=db_obj.timestamp,
        )

    async def create(self, db: AsyncSession, *, obj_in: TradeEntity) -> TradeEntity:
        db_obj = self.model(
            id=obj_in.id,
            order_id=obj_in.order_id,
            symbol=obj_in.symbol,
            price=obj_in.price,
            quantity=obj_in.quantity,
            timestamp=obj_in.timestamp,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return self._to_domain(db_obj)

    async def upsert_bulk(self, session: AsyncSession, trades_data: list[dict]):
        if not trades_data:
            return

        stmt = insert(DbTrade).values(trades_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        await session.execute(stmt)


trade_repo = TradeRepository(DbTrade)

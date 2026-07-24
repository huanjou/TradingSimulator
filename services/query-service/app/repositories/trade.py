from app.models.trade import Trade
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TradeRepository:
    async def get_by_order_id(
        self, session: AsyncSession, order_id: str, limit: int = 50, offset: int = 0
    ) -> list[Trade]:
        stmt = (
            select(Trade)
            .where(Trade.order_id == order_id)
            .order_by(Trade.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_by_user_id(
        self, session: AsyncSession, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[Trade]:
        from app.models.order import Order

        stmt = (
            select(Trade)
            .join(Order, Trade.order_id == Order.id)
            .where(Order.user_id == user_id)
            .order_by(Trade.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


trade_repo = TradeRepository()

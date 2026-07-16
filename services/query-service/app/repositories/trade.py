from app.models.trade import Trade
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TradeRepository:
    async def get_by_order_id(
        self, session: AsyncSession, order_id: str
    ) -> list[Trade]:
        stmt = (
            select(Trade)
            .where(Trade.order_id == order_id)
            .order_by(Trade.timestamp.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()


trade_repo = TradeRepository()

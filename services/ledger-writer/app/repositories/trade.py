from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade


class TradeRepository:
    async def upsert_bulk(self, session: AsyncSession, trades_data: list[dict]):
        if not trades_data:
            return

        stmt = insert(Trade).values(trades_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        await session.execute(stmt)


trade_repo = TradeRepository()

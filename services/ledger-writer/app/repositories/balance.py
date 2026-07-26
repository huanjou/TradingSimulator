from app.models.balance import Balance
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession


class BalanceRepository:
    async def upsert_bulk(self, session: AsyncSession, balances_data: list[dict]):
        if not balances_data:
            return

        stmt = insert(Balance).values(balances_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "currency"],
            set_=dict(available=stmt.excluded.available, locked=stmt.excluded.locked),
        )
        await session.execute(stmt)


balance_repo = BalanceRepository()

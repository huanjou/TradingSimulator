from app.models.balance import Balance
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession


class BalanceRepository:
    async def upsert_bulk(self, session: AsyncSession, balances_data: list[dict]):
        if not balances_data:
            return

        dialect = (
            session.bind.dialect.name
            if session.bind
            else session.get_bind().dialect.name
        )
        if dialect == "sqlite":
            stmt = sqlite_insert(Balance).values(balances_data)
        else:
            stmt = pg_insert(Balance).values(balances_data)

        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "currency"],
            set_=dict(available=stmt.excluded.available, locked=stmt.excluded.locked),
        )
        await session.execute(stmt)


balance_repo = BalanceRepository()

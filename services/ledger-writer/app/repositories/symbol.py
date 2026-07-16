from app.models.symbol import Symbol
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession


class SymbolRepository:
    async def upsert(
        self, session: AsyncSession, symbol_name: str, is_active: bool = True
    ):
        stmt = insert(Symbol).values(name=symbol_name, is_active=is_active)
        stmt = stmt.on_conflict_do_update(
            index_elements=["name"], set_={"is_active": is_active}
        )
        await session.execute(stmt)


symbol_repo = SymbolRepository()

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.models.symbol import Symbol

router = APIRouter()


class SymbolResponse(BaseModel):
    name: str
    is_active: bool


@router.get("", response_model=list[SymbolResponse])
async def get_symbols(
    q: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Symbol).where(Symbol.is_active)

    if q:
        stmt = stmt.where(Symbol.name.ilike(f"%{q}%"))

    stmt = stmt.order_by(Symbol.name).limit(limit).offset(offset)

    result = await db.execute(stmt)
    symbols = result.scalars().all()

    return [{"name": s.name, "is_active": s.is_active} for s in symbols]

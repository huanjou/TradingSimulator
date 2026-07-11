from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.models.symbol import Symbol

router = APIRouter()


class SymbolResponse(BaseModel):
    name: str
    is_active: bool


@router.get("/", response_model=list[SymbolResponse])
async def get_symbols(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Symbol).where(Symbol.is_active == True))
    symbols = result.scalars().all()
    return [{"name": s.name, "is_active": s.is_active} for s in symbols]

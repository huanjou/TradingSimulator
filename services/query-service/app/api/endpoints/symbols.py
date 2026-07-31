import json

import structlog
from app.core.redis import redis_client
from app.db.session import get_db
from app.models.symbol import Symbol
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = structlog.get_logger(__name__)

router = APIRouter()


class SymbolResponse(BaseModel):
    name: str
    is_active: bool
    last_price: float | None = None


async def _get_last_prices(names: list[str]) -> dict[str, float]:
    """
    Fetches last known mid prices from Redis (written by stream-service on
    every market tick). Best-effort: a Redis outage must not break the
    symbols endpoint, prices just come back as None.
    """
    if not names:
        return {}
    try:
        raw_values = await redis_client.mget([f"last_price:{n}" for n in names])
    except Exception as e:
        logger.error("last_price_cache_read_failed", error=str(e), exc_info=True)
        return {}

    prices: dict[str, float] = {}
    for name, raw in zip(names, raw_values):
        if not raw:
            continue
        try:
            tick = json.loads(raw)
            mid = (float(tick["bid_price"]) + float(tick["ask_price"])) / 2
            prices[name] = round(mid, 2)
        except (ValueError, TypeError, KeyError) as e:
            logger.warning("invalid_last_price_payload", symbol=name, error=str(e))
    return prices


@router.get("", response_model=list[SymbolResponse])
async def get_symbols(
    # NOTE: intentionally unauthenticated — symbols are public market reference
    # data and are fetched by the market-data service without a user JWT.
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

    last_prices = await _get_last_prices([s.name for s in symbols])

    return [
        {
            "name": s.name,
            "is_active": s.is_active,
            "last_price": last_prices.get(s.name),
        }
        for s in symbols
    ]

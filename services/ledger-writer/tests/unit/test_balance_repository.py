from decimal import Decimal

import pytest
from app.models import Base
from app.models.balance import Balance
from app.repositories.balance import BalanceRepository
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_bulk(db_session):
    repo = BalanceRepository()

    # Insert new
    updates = [
        {"user_id": "u1", "currency": "USD", "available": "100.0", "locked": "10.0"},
        {"user_id": "u1", "currency": "BTC", "available": "1.5", "locked": "0.0"},
    ]

    await repo.upsert_bulk(db_session, updates)
    await db_session.commit()
    db_session.expire_all()

    from sqlalchemy import select

    result = await db_session.execute(select(Balance).where(Balance.user_id == "u1"))
    balances = result.scalars().all()

    assert len(balances) == 2

    # Update existing
    updates_2 = [
        {"user_id": "u1", "currency": "USD", "available": "200.0", "locked": "5.0"},
    ]

    await repo.upsert_bulk(db_session, updates_2)
    await db_session.commit()
    db_session.expire_all()

    result = await db_session.execute(
        select(Balance).where(Balance.user_id == "u1", Balance.currency == "USD")
    )
    usd_balance = result.scalar_one()

    assert Decimal(str(usd_balance.available)) == Decimal("200.0")
    assert Decimal(str(usd_balance.locked)) == Decimal("5.0")

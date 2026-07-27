import pytest
from app.repositories.balance import BalanceRepository
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.balance import Balance
from app.models import Base

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
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
        {"user_id": "u1", "currency": "BTC", "available": "1.5", "locked": "0.0"}
    ]
    
    await repo.upsert_bulk(db_session, updates)
    await db_session.commit()
    
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
    
    result = await db_session.execute(select(Balance).where(Balance.user_id == "u1", Balance.currency == "USD"))
    usd_balance = result.scalar_one()
    
    assert str(usd_balance.available) == "200.00000000"
    assert str(usd_balance.locked) == "5.00000000"

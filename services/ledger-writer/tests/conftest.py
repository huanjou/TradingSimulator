import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "POSTGRES_URL", "postgresql+asyncpg://admin:password@127.0.0.1:5432/ledger_db"
)
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("KAFKA_BROKER", "127.0.0.1:9092")
os.environ.setdefault("ENV", "test")


@pytest_asyncio.fixture()
async def engine():
    engine = create_async_engine(os.environ["POSTGRES_URL"])
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(engine):
    connection = await engine.connect()
    # Begin a non-ORM transaction
    trans = await connection.begin()

    async_session = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        class_=AsyncSession,
        join_transaction_mode="create_savepoint",
    )
    session = async_session()

    yield session

    await session.close()
    await trans.rollback()
    await connection.close()


@pytest.fixture(autouse=True)
def override_session_local(db_session, monkeypatch):
    class MockSessionManager:
        def __call__(self, *args, **kwargs):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_manager = MockSessionManager()
    monkeypatch.setattr("app.services.processor.AsyncSessionLocal", mock_manager)

import asyncio
import os
from urllib.parse import urlparse, urlunparse

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 1. We extract the host/port from the default POSTGRES_URL or environment,
# and replace the database name with test_ledger_db.
# Crucially, query-service points to postgres-replica by default, but we need primary to create DB and run tests safely without replication lag.  # noqa: E501
original_url = os.environ.get(
    "POSTGRES_URL", "postgresql+asyncpg://admin:password@127.0.0.1:5432/ledger_db"
)
original_url = original_url.replace("postgres-replica", "postgres-primary")
parsed = urlparse(original_url)
test_db_url = urlunparse(parsed._replace(path="/test_ledger_db"))
sys_db_url = urlunparse(parsed._replace(scheme="postgresql"))

os.environ["POSTGRES_URL"] = test_db_url

# 2. Use a separate Redis database (e.g. 1) for tests so we don't wipe dev cache!
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/1")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test_secret_for_tests")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    import asyncpg

    # Connect to default postgres DB to create test_ledger_db if not exists
    sys_conn = await asyncpg.connect(sys_db_url)
    try:
        await sys_conn.execute("CREATE DATABASE test_ledger_db")
    except asyncpg.exceptions.DuplicateDatabaseError:
        pass
    finally:
        await sys_conn.close()

    # Run create_all to create tables since we don't have alembic in this container
    from app.db.base_class import Base

    engine = create_async_engine(test_db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


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

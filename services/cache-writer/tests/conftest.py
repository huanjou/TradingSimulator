import asyncio
import os
import subprocess
from urllib.parse import urlparse, urlunparse

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# We extract the host/port from the default POSTGRES_URL or environment,
# and replace the database name with test_ledger_db.
original_url = os.environ.get(
    "POSTGRES_URL", "postgresql+asyncpg://admin:password@127.0.0.1:5432/ledger_db"
)
parsed = urlparse(original_url)
test_db_url = urlunparse(parsed._replace(path="/test_ledger_db"))
# Use the original db to connect and create the test db, because the default 'postgres' might not be accessible.
sys_db_url = urlunparse(parsed._replace(scheme="postgresql"))

os.environ["POSTGRES_URL"] = test_db_url
# Use test Redis DB (e.g. 1) to prevent overwriting dev cache
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/1")
os.environ.setdefault("KAFKA_BROKER", "127.0.0.1:9092")
os.environ.setdefault("ENV", "test")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    import asyncpg

    # 1. Connect to default postgres DB to create test_ledger_db if not exists
    sys_conn = await asyncpg.connect(sys_db_url)
    try:
        await sys_conn.execute("CREATE DATABASE test_ledger_db")
    except asyncpg.exceptions.DuplicateDatabaseError:
        pass
    finally:
        await sys_conn.close()

    # 2. Run alembic migrations on the newly created test_ledger_db
    subprocess.run(["alembic", "upgrade", "head"], check=True)


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

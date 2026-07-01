import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, engine, get_db
from app.main import app


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """
    Creates a new database session with a savepoint for each test.
    This allows rolling back changes after the test finishes, ensuring isolation.
    """
    async with engine.connect() as conn:
        transaction = await conn.begin()
        await conn.begin_nested()  # Start a nested transaction (savepoint)

        async_session = AsyncSessionLocal(
            bind=conn, join_transaction_mode="create_savepoint"
        )

        yield async_session

        await async_session.close()
        await transaction.rollback()


from tests.factories import OrderFactory, UserFactory


@pytest_asyncio.fixture
async def user_factory(db_session: AsyncSession):
    """
    Fixture for persisting User instances dynamically in tests using factory_boy.
    """

    async def _create_user(**kwargs):
        user = UserFactory.build(**kwargs)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _create_user


@pytest_asyncio.fixture
async def order_factory(db_session: AsyncSession, user_factory):
    """
    Fixture for persisting Order instances dynamically in tests using factory_boy.
    """

    async def _create_order(**kwargs):
        if "user_id" not in kwargs:
            user = await user_factory()
            kwargs["user_id"] = user.id

        order = OrderFactory.build(**kwargs)
        db_session.add(order)
        await db_session.commit()
        await db_session.refresh(order)
        return order

    return _create_order


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """
    Fixture that provides an AsyncClient for testing FastAPI endpoints.
    Overrides get_db to use the test session with savepoints.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    app.dependency_overrides.clear()

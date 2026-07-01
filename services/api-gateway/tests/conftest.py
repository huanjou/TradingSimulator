import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def user_factory():
    """
    Fixture for creating mock User data without DB persistence.
    """

    async def _create_user(**kwargs):
        class MockUser:
            def __init__(self, **kwargs):
                self.id = kwargs.get("id", uuid.uuid4())

        return MockUser(**kwargs)

    return _create_user


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """
    Fixture that provides an AsyncClient for testing FastAPI endpoints.
    """
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

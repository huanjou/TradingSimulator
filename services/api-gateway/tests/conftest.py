import uuid

import pytest_asyncio
from app.main import app
from httpx import ASGITransport, AsyncClient


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


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, user_factory):
    from app.core.config import get_settings
    from jose import jwt

    user = await user_factory()
    token = jwt.encode(
        {"sub": str(user.id)}, get_settings().JWT_SECRET, algorithm="HS256"
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client, user


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, user_factory):
    from app.core.config import get_settings
    from jose import jwt

    admin_user = await user_factory()
    token = jwt.encode(
        {"sub": str(admin_user.id), "role": "admin"},
        get_settings().JWT_SECRET,
        algorithm="HS256",
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client, admin_user

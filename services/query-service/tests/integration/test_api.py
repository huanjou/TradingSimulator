import os
import uuid

import pytest
from app.db.session import get_db
from app.main import app
from app.models.order import OrderStatusChoice
from httpx import ASGITransport, AsyncClient
from jose import jwt

from tests.factories.models import OrderFactory, UserFactory


def auth_headers(user_id, role: str | None = None) -> dict:
    """Builds an Authorization header with a JWT signed like user-service does."""
    payload = {"sub": str(user_id)}
    if role:
        payload["role"] = role
    token = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_order_from_db(client, db_session):
    # Create user in DB using factory
    user = UserFactory.build()
    db_session.add(user)
    await db_session.flush()

    # Create order in DB using factory
    order = OrderFactory.build(user_id=user.id, status=OrderStatusChoice.PENDING)
    db_session.add(order)
    await db_session.flush()

    # Call API
    response = await client.get(
        f"/api/v1/orders/{order.id}", headers=auth_headers(user.id)
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(order.id)
    assert data["symbol"] == order.symbol
    assert data["quantity"] == order.quantity
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_get_order_from_cache(client, monkeypatch):
    # We mock the get_cached_order service call
    # because if it hits the cache, it returns an OrderEntity directly
    from app.domain.order import OrderEntity

    mock_order = OrderEntity(
        id="c5b24888-297c-4ab4-80cf-f273ed952b65",
        user_id="user1",
        symbol="AAPL",
        side="BUY",
        order_type="LIMIT",
        quantity=10.0,
        price=150.0,
        status="FILLED",
    )

    async def mock_get_cached(*args, **kwargs):
        return mock_order.model_dump(mode="json")

    monkeypatch.setattr("app.services.order_service.get_cached_order", mock_get_cached)

    response = await client.get(
        f"/api/v1/orders/{mock_order.id}", headers=auth_headers("user1")
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(mock_order.id)
    assert data["symbol"] == "AAPL"
    assert data["status"] == "FILLED"


@pytest.mark.asyncio
async def test_get_order_not_found(client, db_session):
    # Call API with nonexistent ID
    response = await client.get(
        "/api/v1/orders/00000000-0000-0000-0000-000000000000",
        headers=auth_headers(uuid.uuid4()),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


@pytest.mark.asyncio
async def test_get_order_requires_auth(client, db_session):
    # No token at all -> 401
    response = await client.get("/api/v1/orders/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_get_order_of_another_user_forbidden(client, db_session):
    user = UserFactory.build()
    db_session.add(user)
    await db_session.flush()

    order = OrderFactory.build(user_id=user.id, status=OrderStatusChoice.PENDING)
    db_session.add(order)
    await db_session.flush()

    # Authenticated as a different user -> 403
    response = await client.get(
        f"/api/v1/orders/{order.id}", headers=auth_headers(uuid.uuid4())
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to access this order"


@pytest.mark.asyncio
async def test_get_order_as_admin(client, db_session):
    user = UserFactory.build()
    db_session.add(user)
    await db_session.flush()

    order = OrderFactory.build(user_id=user.id, status=OrderStatusChoice.PENDING)
    db_session.add(order)
    await db_session.flush()

    # Admins may read any order
    response = await client.get(
        f"/api/v1/orders/{order.id}", headers=auth_headers(uuid.uuid4(), role="admin")
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(order.id)


@pytest.mark.asyncio
async def test_get_pending_orders_requires_admin(client, db_session):
    # Regular user -> 403
    response = await client.get(
        "/api/v1/orders/pending", headers=auth_headers(uuid.uuid4())
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"

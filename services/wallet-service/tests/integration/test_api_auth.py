import time

import pytest
from app.core.config import settings
from app.main import app
from httpx import AsyncClient
from jose import jwt


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_auth_missing_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/wallets/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_auth_invalid_token():
    headers = {"Authorization": "Bearer invalid.jwt.token"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/wallets/me", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_expired_token():
    payload = {"sub": "user1", "exp": int(time.time()) - 3600}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/wallets/me", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_csrf_protection_on_post_via_cookie():
    payload = {"sub": "user1", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    cookies = {"access_token": token, "csrf_token": "valid_csrf_token"}
    # Отправляем POST запрос без X-CSRF-Token заголовка
    async with AsyncClient(app=app, base_url="http://test", cookies=cookies) as client:
        response = await client.post(
            "/api/v1/wallets/deposit", json={"currency": "USD", "amount": 100}
        )
    assert response.status_code == 403
    assert "CSRF token missing or incorrect" in response.json()["detail"]

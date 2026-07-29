import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.domain.user import User as DomainUser
from app.services.auth import (
    InvalidRefreshTokenException,
    refresh_access_token_service,
)
from jose import jwt


def _user(**overrides) -> DomainUser:
    defaults = {
        "id": uuid.uuid4(),
        "email": "trader@example.com",
        "hashed_password": "hashed",
        "is_active": True,
        "is_superuser": False,
        "token_version": 1,
    }
    defaults.update(overrides)
    return DomainUser(**defaults)


def _repo_returning(user):
    """Patches the repository used by the auth service to return `user`."""
    repo = AsyncMock()
    repo.get_by_id.return_value = user
    return patch("app.services.auth.UserRepository", return_value=repo), repo


def _decode(token: str) -> dict:
    return jwt.decode(
        token,
        settings.JWT_SECRET.get_secret_value(),
        algorithms=[settings.JWT_ALGORITHM],
    )


async def test_refresh_issues_new_access_token():
    user = _user(token_version=3)
    token = create_refresh_token(subject=str(user.id), token_version=3)
    patcher, repo = _repo_returning(user)

    with patcher:
        access_token = await refresh_access_token_service(AsyncMock(), token)

    payload = _decode(access_token)
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "user"
    # The issued token is an access token, not another refresh token.
    assert "type" not in payload
    repo.get_by_id.assert_awaited_once_with(str(user.id))


async def test_refresh_preserves_admin_role():
    user = _user(is_superuser=True, token_version=2)
    token = create_refresh_token(subject=str(user.id), token_version=2)
    patcher, _ = _repo_returning(user)

    with patcher:
        access_token = await refresh_access_token_service(AsyncMock(), token)

    assert _decode(access_token)["role"] == "admin"


async def test_refresh_rejects_invalid_token():
    patcher, repo = _repo_returning(_user())

    with patcher, pytest.raises(InvalidRefreshTokenException):
        await refresh_access_token_service(AsyncMock(), "garbage")

    # An unparseable token must be rejected before touching the database.
    repo.get_by_id.assert_not_awaited()


async def test_refresh_rejects_access_token_used_as_refresh():
    user = _user()
    access_token = create_access_token(subject=str(user.id))
    patcher, repo = _repo_returning(user)

    with patcher, pytest.raises(InvalidRefreshTokenException):
        await refresh_access_token_service(AsyncMock(), access_token)

    repo.get_by_id.assert_not_awaited()


async def test_refresh_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", -1)
    user = _user()
    token = create_refresh_token(subject=str(user.id), token_version=1)
    patcher, _ = _repo_returning(user)

    with patcher, pytest.raises(InvalidRefreshTokenException):
        await refresh_access_token_service(AsyncMock(), token)


async def test_refresh_rejects_unknown_user():
    token = create_refresh_token(subject=str(uuid.uuid4()), token_version=1)
    patcher, _ = _repo_returning(None)

    with patcher, pytest.raises(InvalidRefreshTokenException):
        await refresh_access_token_service(AsyncMock(), token)


async def test_refresh_rejects_deactivated_user():
    user = _user(is_active=False)
    token = create_refresh_token(subject=str(user.id), token_version=1)
    patcher, _ = _repo_returning(user)

    with patcher, pytest.raises(InvalidRefreshTokenException):
        await refresh_access_token_service(AsyncMock(), token)


async def test_refresh_rejects_revoked_token_version():
    # The user's token_version was bumped (e.g. password change), so every
    # refresh token issued before that is revoked.
    user = _user(token_version=5)
    stale_token = create_refresh_token(subject=str(user.id), token_version=4)
    patcher, _ = _repo_returning(user)

    with patcher, pytest.raises(InvalidRefreshTokenException, match="revoked"):
        await refresh_access_token_service(AsyncMock(), stale_token)


async def test_refresh_rejects_forged_token_version():
    # Bumping the version claim in a forged token does not help: the signature
    # check fails first.
    user = _user(token_version=5)
    forged = jwt.encode(
        {"sub": str(user.id), "type": "refresh", "version": 5},
        "attacker_secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    patcher, _ = _repo_returning(user)

    with patcher, pytest.raises(InvalidRefreshTokenException):
        await refresh_access_token_service(AsyncMock(), forged)


async def test_refresh_rejects_token_without_subject():
    token = jwt.encode(
        {"type": "refresh", "version": 1},
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    patcher, repo = _repo_returning(_user())

    with patcher, pytest.raises(InvalidRefreshTokenException):
        await refresh_access_token_service(AsyncMock(), token)

    repo.get_by_id.assert_not_awaited()

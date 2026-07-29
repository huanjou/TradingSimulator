from datetime import timedelta

import pytest
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_access_token,
)
from jose import jwt


def _decode_raw(token: str) -> dict:
    return jwt.decode(
        token,
        settings.JWT_SECRET.get_secret_value(),
        algorithms=[settings.JWT_ALGORITHM],
    )


def test_refresh_token_carries_type_and_version():
    token = create_refresh_token(subject="user-1", token_version=4)
    payload = _decode_raw(token)

    assert payload["sub"] == "user-1"
    assert payload["type"] == "refresh"
    assert payload["version"] == 4


def test_access_token_carries_role_and_no_refresh_type():
    token = create_access_token(subject="user-1", role="admin")
    payload = _decode_raw(token)

    assert payload["sub"] == "user-1"
    assert payload["role"] == "admin"
    assert "type" not in payload


def test_decode_refresh_token_returns_subject_and_version():
    token = create_refresh_token(subject="user-1", token_version=7)
    decoded = decode_refresh_token(token)

    assert decoded is not None
    assert decoded.sub == "user-1"
    assert decoded.version == 7


def test_decode_refresh_token_rejects_access_token():
    # An access token must never be usable to mint further access tokens.
    access_token = create_access_token(subject="user-1")
    assert decode_refresh_token(access_token) is None


def test_decode_refresh_token_rejects_garbage():
    assert decode_refresh_token("not-a-jwt") is None


def test_decode_refresh_token_rejects_foreign_signature():
    token = jwt.encode(
        {"sub": "user-1", "type": "refresh", "version": 1},
        "a_completely_different_secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_refresh_token(token) is None


def test_decode_refresh_token_rejects_expired(monkeypatch):
    # A negative lifetime yields an already-expired token.
    monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", -1)
    token = create_refresh_token(subject="user-1", token_version=1)
    assert decode_refresh_token(token) is None


def test_verify_access_token_rejects_refresh_token():
    # Privilege separation: the long-lived refresh token must not authenticate
    # regular API calls.
    refresh_token = create_refresh_token(subject="user-1", token_version=1)
    assert verify_access_token(refresh_token) is None


def test_verify_access_token_accepts_access_token():
    token = create_access_token(subject="user-1")
    assert verify_access_token(token) == "user-1"


def test_verify_access_token_accepts_legacy_token_without_type():
    # Tokens issued before refresh tokens existed carry no "type" claim and
    # must stay valid until they expire.
    legacy = jwt.encode(
        {"sub": "user-legacy", "role": "user"},
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    assert verify_access_token(legacy) == "user-legacy"


def test_verify_access_token_rejects_expired_access_token():
    token = create_access_token(subject="user-1", expires_delta=timedelta(minutes=-5))
    assert verify_access_token(token) is None


@pytest.mark.parametrize("bad_token", ["", "a.b.c", "Bearer something"])
def test_verify_access_token_rejects_malformed(bad_token):
    assert verify_access_token(bad_token) is None

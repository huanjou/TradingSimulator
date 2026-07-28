from datetime import datetime, timedelta
from typing import Any

from app.core.config import settings
from app.schemas.user import RefreshTokenPayload, TokenPayload
from jose import JWTError, jwt
from passlib.context import CryptContext
from starlette.concurrency import run_in_threadpool

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def _verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _get_password_hash_sync(password: str) -> str:
    return pwd_context.hash(password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return await run_in_threadpool(
        _verify_password_sync, plain_password, hashed_password
    )


async def get_password_hash(password: str) -> str:
    return await run_in_threadpool(_get_password_hash_sync, password)


def create_access_token(
    subject: str | Any, expires_delta: timedelta | None = None, role: str = "user"
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "role": role}
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def verify_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
        # A refresh token must never be accepted as an access token. Legacy
        # long-lived access tokens carry no "type" claim and remain valid
        # until they expire (backward compatibility).
        if payload.get("type") == "refresh":
            return None
        token_data = TokenPayload(**payload)
        return str(token_data.sub)
    except JWTError:
        return None


def create_refresh_token(subject: str | Any, token_version: int) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "version": token_version,
    }
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_refresh_token(token: str) -> RefreshTokenPayload | None:
    """Decode a refresh token. Returns None if invalid, expired or wrong type."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None
    if payload.get("type") != "refresh":
        return None
    return RefreshTokenPayload(sub=payload.get("sub"), version=payload.get("version"))

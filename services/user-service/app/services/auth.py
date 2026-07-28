import secrets

from app.core.rate_limit import (
    ensure_not_locked,
    register_failure,
    reset,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.domain.user import User as DomainUser
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserLogin
from app.services.user import create_user
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


class UserAlreadyExistsException(Exception):
    pass


class InvalidCredentialsException(Exception):
    pass


class InvalidRefreshTokenException(Exception):
    pass


async def register_user_service(db: AsyncSession, user_in: UserCreate) -> DomainUser:
    repo = UserRepository(db)
    existing_user = await repo.get_by_email(user_in.email)
    if existing_user:
        raise UserAlreadyExistsException(
            "The user with this email already exists in the system."
        )

    return await create_user(db, user_in)


async def login_user_service(
    db: AsyncSession,
    user_in: UserLogin,
    redis: Redis,
    client_ip: str,
) -> dict:
    # Throttle brute-force attempts per (email, ip).
    identifier = f"{user_in.email.lower()}:{client_ip}"
    await ensure_not_locked(redis, identifier)

    repo = UserRepository(db)
    user = await repo.get_by_email(user_in.email)

    if not user or not await verify_password(user_in.password, user.hashed_password):
        await register_failure(redis, identifier)
        raise InvalidCredentialsException("Incorrect email or password")

    # Successful login clears the failure counter.
    await reset(redis, identifier)

    # Short-lived access token; sessions are extended via the refresh token.
    role = "admin" if user.is_superuser else "user"
    access_token = create_access_token(subject=str(user.id), role=role)
    refresh_token = create_refresh_token(
        subject=str(user.id), token_version=user.token_version
    )
    csrf_token = secrets.token_urlsafe(32)

    return {
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "csrf_token": csrf_token,
    }


async def refresh_access_token_service(db: AsyncSession, refresh_token: str) -> str:
    """Validate a refresh token and issue a new short-lived access token."""
    payload = decode_refresh_token(refresh_token)
    if payload is None or payload.sub is None:
        raise InvalidRefreshTokenException("Invalid or expired refresh token")

    repo = UserRepository(db)
    user = await repo.get_by_id(payload.sub)
    if not user or not user.is_active:
        raise InvalidRefreshTokenException("Invalid or expired refresh token")

    # A version mismatch means credentials changed since the token was issued
    # (e.g. password change) — the token is considered revoked.
    if payload.version != user.token_version:
        raise InvalidRefreshTokenException("Refresh token revoked")

    role = "admin" if user.is_superuser else "user"
    return create_access_token(subject=str(user.id), role=role)

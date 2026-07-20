import secrets
from datetime import timedelta

from app.core.security import create_access_token, verify_password
from app.domain.user import User as DomainUser
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserLogin
from app.services.user import create_user
from sqlalchemy.ext.asyncio import AsyncSession


class UserAlreadyExistsException(Exception):
    pass


class InvalidCredentialsException(Exception):
    pass


async def register_user_service(db: AsyncSession, user_in: UserCreate) -> DomainUser:
    repo = UserRepository(db)
    existing_user = await repo.get_by_email(user_in.email)
    if existing_user:
        raise UserAlreadyExistsException(
            "The user with this email already exists in the system."
        )

    return await create_user(db, user_in)


async def login_user_service(db: AsyncSession, user_in: UserLogin) -> dict:
    repo = UserRepository(db)
    user = await repo.get_by_email(user_in.email)

    if not user or not await verify_password(user_in.password, user.hashed_password):
        raise InvalidCredentialsException("Incorrect email or password")

    # Set token expiry based on remember_me flag
    expires_delta = timedelta(days=30) if user_in.remember_me else None
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=expires_delta,
    )
    csrf_token = secrets.token_urlsafe(32)

    return {"user": user, "access_token": access_token, "csrf_token": csrf_token}

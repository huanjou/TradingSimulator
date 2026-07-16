from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    repo = UserRepository(db)
    return await repo.get_by_email(email)


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    repo = UserRepository(db)
    db_obj = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_superuser=False,
    )
    return await repo.create(db_obj)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

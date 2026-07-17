from app.core.security import get_password_hash, verify_password
from app.domain.user import User as DomainUser
from app.models.user import User as DBUser
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_by_email(db: AsyncSession, email: str) -> DomainUser | None:
    repo = UserRepository(db)
    return await repo.get_by_email(email)


async def create_user(db: AsyncSession, user_in: UserCreate) -> DomainUser:
    repo = UserRepository(db)
    db_obj = DBUser(
        email=user_in.email,
        hashed_password=await get_password_hash(user_in.password),
        is_active=True,
        is_superuser=False,
    )
    domain_user = await repo.create(db_obj)
    await db.commit()
    return domain_user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> DomainUser | None:
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        return None
    if not await verify_password(password, user.hashed_password):
        return None
    return user


async def get_user_by_id_cached(
    db: AsyncSession, redis: Redis, user_id: str
) -> UserResponse | None:
    cache_key = f"user:{user_id}"

    # 1. Redis
    cached_user = await redis.get(cache_key)
    if cached_user:
        return UserResponse.model_validate_json(cached_user)

    # 2. DB
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        return None

    # 3. Cache
    user_response = UserResponse.model_validate(user)
    await redis.set(cache_key, user_response.model_dump_json(), ex=300)

    return user_response

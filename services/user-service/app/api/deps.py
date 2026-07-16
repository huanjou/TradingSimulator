from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.repositories.user import UserRepository
from app.schemas.user import TokenPayload, UserResponse
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> UserResponse:
    # Extract token from Header or Cookie
    token: str | None = None
    is_cookie = False

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    if not token:
        token = request.cookies.get("access_token")
        is_cookie = True

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Validate CSRF for modifying requests if token came from cookie
    if is_cookie and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")

        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or incorrect",
            )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
        token_data = TokenPayload(**payload)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from None

    user_id = token_data.sub
    cache_key = f"user:{user_id}"

    # 1. Check Redis Cache
    cached_user = await redis.get(cache_key)
    if cached_user:
        return UserResponse.model_validate_json(cached_user)

    # 2. Cache Miss -> Check DB
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 3. Save to Redis
    user_response = UserResponse.model_validate(user)
    # Cache for 5 mins
    await redis.set(cache_key, user_response.model_dump_json(), ex=300)

    return user_response

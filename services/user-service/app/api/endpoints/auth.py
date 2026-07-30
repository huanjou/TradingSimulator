from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth import (
    InvalidRefreshTokenException,
    login_user_service,
    refresh_access_token_service,
    register_user_service,
)
from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

# The refresh cookie is scoped to this exact path so browsers only send it
# to the refresh endpoint, never with regular API requests.
REFRESH_COOKIE_PATH = "/api/v1/auth/refresh"


def _client_ip(request: Request) -> str:
    """Resolve the real client IP when running behind the nginx proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await register_user_service(db, user_in)
    return user


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    user_in: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    result = await login_user_service(db, user_in, redis, _client_ip(request))

    # If remember_me is True, cookies persist for the refresh token lifetime.
    # Otherwise they are session cookies (cleared when the browser closes).
    if user_in.remember_me:
        cookie_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    else:
        cookie_max_age = None

    # Set HTTP-only cookie for the short-lived access token
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        max_age=cookie_max_age,
        samesite="strict",
        secure=settings.COOKIE_SECURE,
        path="/",
    )

    # Set HTTP-only cookie for the refresh token, scoped to the refresh
    # endpoint only so it is not sent with every request.
    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        max_age=cookie_max_age,
        samesite="strict",
        secure=settings.COOKIE_SECURE,
        path=REFRESH_COOKIE_PATH,
    )

    # Set non-HTTP-only cookie for CSRF token so JS can read it
    response.set_cookie(
        key="csrf_token",
        value=result["csrf_token"],
        httponly=False,
        max_age=cookie_max_age,
        samesite="strict",
        secure=settings.COOKIE_SECURE,
        path="/",
    )

    # The access token lives ONLY in the HTTP-only cookie above. It is
    # intentionally NOT returned in the response body so it cannot be read
    # by JavaScript (defends against XSS token theft).
    return {
        "token_type": "bearer",
        "user_id": str(result["user"].id),
    }


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise InvalidRefreshTokenException("No refresh token")

    new_access_token = await refresh_access_token_service(db, refresh_token)

    # Persist for the token lifetime so the cookie survives a browser
    # restart within that window; the browser drops it once it expires.
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="strict",
        secure=settings.COOKIE_SECURE,
        path="/",
    )
    return {"status": "refreshed"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    response.delete_cookie(
        key="refresh_token",
        path=REFRESH_COOKIE_PATH,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=False,
        samesite="strict",
    )
    return {"detail": "Successfully logged out"}

from app.core.config import settings
from app.db.session import get_db
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth import (
    login_user_service,
    register_user_service,
)
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await register_user_service(db, user_in)
    return user


@router.post("/login")
async def login(
    response: Response, user_in: UserLogin, db: AsyncSession = Depends(get_db)
):
    result = await login_user_service(db, user_in)

    # Set HTTP-only cookie for access token
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        max_age=7 * 24 * 60 * 60,  # 7 days
        samesite="strict",
        secure=settings.COOKIE_SECURE,
        path="/",
    )

    # Set non-HTTP-only cookie for CSRF token so JS can read it
    response.set_cookie(
        key="csrf_token",
        value=result["csrf_token"],
        httponly=False,
        max_age=7 * 24 * 60 * 60,
        samesite="strict",
        secure=settings.COOKIE_SECURE,
        path="/",
    )

    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
        "user_id": str(result["user"].id),
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="csrf_token")
    return {"detail": "Successfully logged out"}

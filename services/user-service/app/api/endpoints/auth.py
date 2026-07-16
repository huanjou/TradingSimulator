import secrets

from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.user import authenticate_user, create_user, get_user_by_email
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    user = await create_user(db, user_in=user_in)
    return user


@router.post("/login")
async def login(
    response: Response, user_in: UserLogin, db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, email=user_in.email, password=user_in.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = create_access_token(subject=str(user.id))
    csrf_token = secrets.token_urlsafe(32)

    # Set HTTP-only cookie for access token
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,  # 7 days
        samesite="lax",  # or "strict"
        secure=False,  # Set to True in production with HTTPS
        path="/",
    )

    # Set non-HTTP-only cookie for CSRF token so JS can read it
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        max_age=7 * 24 * 60 * 60,
        samesite="lax",
        secure=False,
        path="/",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="csrf_token")
    return {"detail": "Successfully logged out"}

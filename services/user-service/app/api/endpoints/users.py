from app.api.deps import get_current_user
from app.schemas.user import UserResponse
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: UserResponse = Depends(get_current_user)):
    return current_user

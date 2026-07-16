from app.core.config import settings
from fastapi import APIRouter

router = APIRouter()


@router.get("", tags=["Health"])
def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}

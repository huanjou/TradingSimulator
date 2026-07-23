from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["System"])
async def health_check() -> dict:
    """
    Check if the service is running.
    """
    return {"status": "healthy"}

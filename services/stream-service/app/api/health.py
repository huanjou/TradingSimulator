from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.kafka_worker import kafka_worker

router = APIRouter()


@router.get("/health", tags=["System"])
async def health_check():
    """
    Liveness + readiness check: verifies the Kafka consume loop is alive.
    """
    checks = {}

    # Check Kafka: the background consume loop must still be running
    checks["kafka"] = "ok" if kafka_worker.is_healthy() else "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )

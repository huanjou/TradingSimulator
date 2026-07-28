from app.core.redis import redis_client
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Liveness + readiness check: verifies Kafka consumer and Redis."""
    checks = {}

    # Check Kafka: the background consumer task must still be running
    consumer_task = getattr(request.app.state, "consumer_task", None)
    checks["kafka"] = "ok" if consumer_task and not consumer_task.done() else "error"

    # Check Redis
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )


@router.get("/ready")
async def readiness_check():
    return {"status": "ready"}

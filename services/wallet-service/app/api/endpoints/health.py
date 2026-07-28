from app.core.kafka import kafka_client
from app.core.redis import redis_client
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("")
async def health_check():
    """Liveness + readiness check: verifies Kafka and Redis connectivity."""
    checks = {}

    # Check Kafka: cheap metadata fetch through the producer client
    try:
        if kafka_client.producer is None:
            raise RuntimeError("Kafka producer not initialized")
        await kafka_client.producer.client.fetch_all_metadata()
        checks["kafka"] = "ok"
    except Exception:
        checks["kafka"] = "error"

    # Check Redis
    try:
        if redis_client.client is None:
            raise RuntimeError("Redis is not initialized")
        await redis_client.client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )

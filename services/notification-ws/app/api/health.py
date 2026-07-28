from app.services.kafka_consumer import notification_consumer
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check():
    """Liveness + readiness check: verifies the Kafka consume loop is alive."""
    checks = {}

    # Check Kafka: the background consumer task must still be running
    checks["kafka"] = (
        "ok"
        if notification_consumer.task and not notification_consumer.task.done()
        else "error"
    )

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )

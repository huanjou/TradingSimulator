import grpc
from app.core.kafka import kafka_client
from app.core.redis import redis_client
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/")
async def health_check(request: Request):
    """
    Liveness + readiness check: verifies Kafka, Redis (if initialized)
    and the gRPC channel to query-service.
    """
    checks = {}

    # Check Kafka: cheap metadata fetch through the producer client
    try:
        if kafka_client.producer is None:
            raise RuntimeError("Kafka producer not initialized")
        await kafka_client.producer.client.fetch_all_metadata()
        checks["kafka"] = "ok"
    except Exception:
        checks["kafka"] = "error"

    # Check Redis (optional: only when the rate-limiter client is initialized)
    if redis_client.client is not None:
        try:
            await redis_client.client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"

    # Check upstream query-service gRPC channel
    try:
        state = request.app.state.grpc_channel.get_state()
        checks["query_service_grpc"] = (
            "error"
            if state
            in (
                grpc.ChannelConnectivity.TRANSIENT_FAILURE,
                grpc.ChannelConnectivity.SHUTDOWN,
            )
            else "ok"
        )
    except Exception:
        checks["query_service_grpc"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )

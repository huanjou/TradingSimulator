from fastapi import APIRouter

from app.core.kafka import kafka_client

router = APIRouter()


@router.get("/")
async def health_check():
    """
    Check system health, including Kafka connection.
    """
    health_status = {"status": "ok", "kafka": "unknown"}

    # Check Kafka
    if kafka_client.producer:
        health_status["kafka"] = "connected"
    else:
        health_status["kafka"] = "not_initialized"

    return health_status

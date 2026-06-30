from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.kafka import kafka_client
from app.db.session import get_db

router = APIRouter()


@router.get("/")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Check system health, including DB and Kafka connections.
    """
    health_status = {"status": "ok", "db": "unknown", "kafka": "unknown"}

    # Check DB
    try:
        await db.execute(text("SELECT 1"))
        health_status["db"] = "connected"
    except Exception as e:
        health_status["db"] = f"error: {str(e)}"

    # Check Kafka
    if kafka_client.producer:
        health_status["kafka"] = "connected"
    else:
        health_status["kafka"] = "not_initialized"

    return health_status

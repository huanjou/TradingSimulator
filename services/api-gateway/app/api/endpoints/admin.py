import json

from aiokafka import AIOKafkaProducer
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


class SymbolCreateRequest(BaseModel):
    symbol: str


async def get_kafka_producer():
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()


from app.services.admin import AdminService


async def get_admin_service(producer: AIOKafkaProducer = Depends(get_kafka_producer)):
    return AdminService(producer)


@router.post("/symbols")
async def create_symbol(
    request: SymbolCreateRequest,
    admin_service: AdminService = Depends(get_admin_service),
):
    try:
        await admin_service.create_symbol(request.symbol)
        return {
            "status": "success",
            "message": f"Symbol {request.symbol} creation event published",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

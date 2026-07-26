from contextlib import asynccontextmanager

from app.api.router import api_router
from app.core.config import settings
from app.core.kafka import kafka_client
from app.core.redis import redis_client
from app.services.kafka_consumer import balance_consumer
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await kafka_client.start()
    await redis_client.connect(settings.REDIS_URL)
    await balance_consumer.start()
    yield
    # Shutdown
    await balance_consumer.stop()
    await kafka_client.stop()
    await redis_client.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix="/api/v1")

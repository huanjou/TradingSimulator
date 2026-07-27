from contextlib import asynccontextmanager

import structlog
from app.api.router import api_router
from app.core.config import settings
from app.core.kafka import kafka_client
from app.core.logging import setup_logging
from app.core.middleware import setup_middlewares
from app.core.redis import redis_client
from app.core.telemetry import setup_opentelemetry
from app.services.kafka_consumer import balance_consumer
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

setup_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


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

# Setup middlewares (CORS, Logging)
setup_middlewares(app)

# Instrument FastAPI with OpenTelemetry traces
setup_opentelemetry(app)

# Instrument FastAPI with Prometheus metrics
Instrumentator().instrument(app).expose(app)


app.include_router(api_router, prefix="/api/v1")

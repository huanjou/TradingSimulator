from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.kafka import kafka_client
from app.core.logging import setup_logging
from app.core.middleware import setup_middlewares
from app.core.telemetry import setup_opentelemetry

settings = get_settings()

setup_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to Kafka
    logger.info("Starting up API Gateway...")
    try:
        await kafka_client.start()
    except Exception as e:
        logger.error(f"Failed to start Kafka client: {e}")

    yield

    # Shutdown: Disconnect from Kafka
    logger.info("Shutting down API Gateway...")
    await kafka_client.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Initialize OpenTelemetry Instrumentation
setup_opentelemetry(app)

# Initialize Middlewares (CORS, etc)
setup_middlewares(app)

app.include_router(api_router, prefix=settings.API_V1_STR)

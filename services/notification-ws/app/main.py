from contextlib import asynccontextmanager

import structlog
from app.api import ws
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middlewares
from app.core.telemetry import setup_opentelemetry
from app.services.kafka_consumer import notification_consumer
from fastapi import FastAPI

settings = get_settings()

setup_logging(settings.LOG_LEVEL if hasattr(settings, "LOG_LEVEL") else "INFO")

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Kafka consumer
    logger.info("starting_notification_ws_service")
    await notification_consumer.start()

    yield

    # Stop Kafka consumer
    logger.info("stopping_notification_ws_service")
    await notification_consumer.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

setup_opentelemetry(app)

setup_middlewares(app)

app.include_router(ws.router, tags=["websocket"])

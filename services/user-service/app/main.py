from contextlib import asynccontextmanager

import structlog
from app.api.api_router import api_router
from app.api.exceptions import setup_exception_handlers
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middlewares
from app.core.redis import redis_client
from app.core.telemetry import setup_opentelemetry
from app.db.session import engine
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

setup_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init Redis
    await redis_client.connect(str(settings.REDIS_URL))

    yield

    # Clean up Redis
    await redis_client.disconnect()

    # Clean up DB
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

# Exception handlers
setup_exception_handlers(app)

# Setup middlewares (CORS, Logging)
setup_middlewares(app)

# Instrument FastAPI with OpenTelemetry traces
setup_opentelemetry(app)

# Instrument FastAPI with Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.include_router(api_router, prefix="/api/v1")

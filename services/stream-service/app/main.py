from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.stream import router as stream_router
from app.core.config import settings
from app.core.telemetry import setup_opentelemetry
from app.services.kafka_worker import kafka_worker
from app.services.streamer import StreamManager

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting stream-service dependencies")

    streamer = StreamManager()
    await streamer.start()
    app.state.streamer = streamer

    await kafka_worker.start()

    yield

    # Shutdown
    logger.info("Shutting down stream-service dependencies")
    await kafka_worker.stop()
    await streamer.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

setup_opentelemetry(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stream_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")

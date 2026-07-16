import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.stream import router as stream_router
from app.core.config import settings
from app.services.kafka_streamer import kafka_streamer

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting stream-service")
    asyncio.create_task(kafka_streamer.start())
    yield
    # Shutdown
    logger.info("Shutting down stream-service")
    await kafka_streamer.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stream_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

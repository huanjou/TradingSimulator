from contextlib import asynccontextmanager

import structlog
from app.api.api_router import api_router
from app.core.config import settings
from app.core.redis import redis_client
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

# Structlog configuration
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.base_class import Base
    from app.db.session import engine

    # Init DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Init Redis
    await redis_client.connect(str(settings.REDIS_URL))

    yield

    # Clean up Redis
    await redis_client.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI with Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.include_router(api_router, prefix="/api/v1")

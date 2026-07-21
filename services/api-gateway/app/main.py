from contextlib import asynccontextmanager

import structlog
from app.api.exceptions import setup_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.kafka import kafka_client
from app.core.logging import setup_logging
from app.core.middleware import setup_middlewares
from app.core.telemetry import setup_opentelemetry
from fastapi import FastAPI

settings = get_settings()

setup_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


import grpc


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to Kafka
    logger.info("Starting up API Gateway...")
    try:
        await kafka_client.start()
    except Exception as e:
        logger.error(f"Failed to start Kafka client: {e}")
        raise  # Fail fast on critical dependency

    # Startup: Initialize Redis for Custom RateLimiter
    try:
        import redis.asyncio as redis
        from app.api import rate_limiter

        rate_limiter.redis_client = redis.from_url(
            str(settings.REDIS_URL), encoding="utf-8", decode_responses=True
        )
        # Verify redis connection
        await rate_limiter.redis_client.ping()
        logger.info("Custom RateLimiter initialized with Redis.")
    except Exception as e:
        logger.error(f"Failed to initialize RateLimiter: {e}")
        raise  # Fail fast

    # Startup: Initialize gRPC Channel
    app.state.grpc_channel = grpc.aio.insecure_channel(settings.QUERY_SERVICE_GRPC_URL)
    logger.info("gRPC channel initialized.")

    yield

    # Shutdown: Disconnect dependencies
    logger.info("Shutting down API Gateway...")
    await app.state.grpc_channel.close()
    await kafka_client.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Initialize Middlewares (CORS, etc)
setup_middlewares(app)

# Initialize Exception Handlers
setup_exception_handlers(app)

# Initialize OpenTelemetry Instrumentation AFTER middlewares so it wraps them
setup_opentelemetry(app)

app.include_router(api_router, prefix=settings.API_V1_STR)

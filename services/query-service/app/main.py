from contextlib import asynccontextmanager

import structlog
from app.api.router import api_router
from app.core.logging import setup_logging
from app.core.telemetry import setup_opentelemetry
from app.grpc_server import serve_grpc
from fastapi import FastAPI

setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start gRPC server in the background
    grpc_server = await serve_grpc()
    yield
    # Stop gRPC server gracefully
    await grpc_server.stop(grace=5)


app = FastAPI(title="Query Service", version="0.1.0", lifespan=lifespan)
setup_opentelemetry(app)

app.include_router(api_router, prefix="/api/v1")

import time

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import settings

logger = structlog.get_logger("api_access")


def setup_middlewares(app: FastAPI):
    """
    Configures all application middlewares
    """

    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=process_time,
        )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=getattr(settings, "BACKEND_CORS_ORIGINS", ["*"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

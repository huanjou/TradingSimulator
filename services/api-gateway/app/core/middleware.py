import time

import structlog
from app.core.config import get_settings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

logger = structlog.get_logger("api_access")
settings = get_settings()


def setup_middlewares(app: FastAPI):
    """
    Configures all application middlewares (CORS, Rate Limiting, etc.)
    """

    # Trust X-Forwarded-For headers from our Nginx proxy
    # The '*' means we trust any proxy (since it's an internal docker network).
    # This automatically updates request.client.host to the user's real IP.
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

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

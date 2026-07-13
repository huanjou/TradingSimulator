import time

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

logger = structlog.get_logger("api_access")


def setup_middlewares(app: FastAPI):
    """
    Configures all application middlewares (CORS, Rate Limiting, etc.)
    """

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
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

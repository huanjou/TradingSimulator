import asyncio

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.telemetry import setup_opentelemetry
from app.db.base import Base  # noqa: F401 (Ensure models are registered)
from app.services.consumer import consume

settings = get_settings()

if __name__ == "__main__":
    setup_logging(log_level=settings.LOG_LEVEL)
    setup_opentelemetry()
    asyncio.run(consume())

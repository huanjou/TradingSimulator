import asyncio
import logging

from app.core.config import get_settings
from app.db.base import *  # This ensures all models are registered
from app.services.consumer import consume

from app.core.logging import setup_logging

settings = get_settings()

if __name__ == "__main__":
    setup_logging(log_level=settings.LOG_LEVEL)
    asyncio.run(consume())

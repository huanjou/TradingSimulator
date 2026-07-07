import asyncio
import logging

from app.core.config import get_settings
from app.db.base import *  # This ensures all models are registered
from app.services.consumer import consume

settings = get_settings()


if __name__ == "__main__":
    logging.basicConfig(level=settings.LOG_LEVEL)
    asyncio.run(consume())

import logging

from fastapi import FastAPI

from app.api.router import api_router
from app.db.base import *  # This ensures all models are registered

logger = logging.getLogger(__name__)

app = FastAPI(title="Query Service", version="0.1.0")

app.include_router(api_router, prefix="/api/v1")

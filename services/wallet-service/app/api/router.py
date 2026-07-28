from app.api.endpoints import health, wallets
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])

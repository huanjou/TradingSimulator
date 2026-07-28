from app.api.endpoints import health, orders, symbols
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(symbols.router, prefix="/symbols", tags=["symbols"])

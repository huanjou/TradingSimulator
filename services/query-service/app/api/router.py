from fastapi import APIRouter

from app.api.endpoints import orders, symbols

api_router = APIRouter()
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(symbols.router, prefix="/symbols", tags=["symbols"])

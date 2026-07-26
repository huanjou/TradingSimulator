from app.api.endpoints import wallets
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])

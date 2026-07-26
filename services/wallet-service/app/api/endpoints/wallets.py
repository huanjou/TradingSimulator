from app.api.deps import get_current_user_id
from app.schemas.wallet import DepositRequest, DepositResponse, WalletsResponse
from app.services.wallet_service import WalletService, get_wallet_service
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/me", response_model=WalletsResponse)
async def get_my_wallets(
    user_id: str = Depends(get_current_user_id),
    service: WalletService = Depends(get_wallet_service),
):
    return await service.get_my_wallets(user_id)


@router.post("/deposit", response_model=DepositResponse)
async def deposit(
    req: DepositRequest,
    user_id: str = Depends(get_current_user_id),
    service: WalletService = Depends(get_wallet_service),
):
    return await service.process_deposit(user_id, req)

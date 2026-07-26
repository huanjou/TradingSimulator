import uuid
import time
from fastapi import HTTPException, Depends
from app.schemas.wallet import DepositRequest, DepositResponse, WalletsResponse, WalletBalance
from app.core.config import settings
from app.core.kafka import kafka_client
from app.repositories.wallet_repository import WalletRepository, get_wallet_repository

class WalletService:
    def __init__(self, repository: WalletRepository):
        self.repository = repository

    async def get_my_wallets(self, user_id: str) -> WalletsResponse:
        entities = await self.repository.get_wallet_balances(user_id)
        balances = [
            WalletBalance(
                currency=e.currency,
                available=str(e.available),
                locked=str(e.locked)
            ) for e in entities
        ]
        return WalletsResponse(balances=balances)

    async def process_deposit(self, user_id: str, req: DepositRequest) -> DepositResponse:
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="Deposit amount must be > 0")

        command = {
            "command_id": str(uuid.uuid4()),
            "user_id": user_id,
            "currency": req.currency,
            "amount": str(req.amount),
            "timestamp": time.time(),
            "type": "DEPOSIT"
        }

        await kafka_client.send_command(
            topic=settings.KAFKA_WALLET_COMMANDS_TOPIC,
            value=command,
            key=user_id.encode("utf-8")
        )

        return DepositResponse(status="success", message="Deposit command queued")

def get_wallet_service(repository: WalletRepository = Depends(get_wallet_repository)) -> WalletService:
    return WalletService(repository)

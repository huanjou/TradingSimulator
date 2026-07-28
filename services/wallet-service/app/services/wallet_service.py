import time
import uuid

from app.core.config import settings
from app.core.kafka import kafka_client
from app.repositories.wallet_repository import WalletRepository, get_wallet_repository
from app.schemas.wallet import (
    DepositRequest,
    DepositResponse,
    WalletBalance,
    WalletsResponse,
)
from fastapi import Depends, HTTPException


class WalletService:
    def __init__(self, repository: WalletRepository):
        self.repository = repository

    async def get_my_wallets(self, user_id: str) -> WalletsResponse:
        entities = await self.repository.get_wallet_balances(user_id)
        balances = [
            WalletBalance(
                currency=e.currency, available=str(e.available), locked=str(e.locked)
            )
            for e in entities
        ]
        return WalletsResponse(balances=balances)

    async def process_deposit(
        self, user_id: str, req: DepositRequest
    ) -> DepositResponse:
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="Deposit amount must be > 0")

        command_id = str(uuid.uuid4())
        # Monotonically increasing per-user version. The trading-engine uses it to
        # causally order this deposit ahead of any order that was placed after it
        # (deposits and orders travel through separate Kafka topics, so an order
        # can otherwise be processed before its funding deposit).
        balance_version = await self.repository.next_balance_version(user_id)
        command = {
            "command_id": command_id,
            "user_id": user_id,
            "currency": req.currency,
            "amount": str(req.amount),
            "timestamp": time.time(),
            "type": "DEPOSIT",
            "balance_version": balance_version,
        }

        await kafka_client.send_command(
            topic=settings.KAFKA_WALLET_COMMANDS_TOPIC,
            value=command,
            key=user_id.encode("utf-8"),
        )

        return DepositResponse(
            status="success",
            message="Deposit command queued",
            command_id=command_id,
            balance_version=balance_version,
        )


def get_wallet_service(
    repository: WalletRepository = Depends(get_wallet_repository),
) -> WalletService:
    return WalletService(repository)

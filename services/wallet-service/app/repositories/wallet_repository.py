from decimal import Decimal

import orjson
import structlog
from app.core.redis import get_redis
from app.domain.wallet import WalletEntity
from fastapi import Depends
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class WalletRepository:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_wallet_balances(self, user_id: str) -> list[WalletEntity]:
        balances = []
        wallet_key = f"wallet:{user_id}"
        raw_wallet = await self.redis.hgetall(wallet_key)

        if not raw_wallet:
            return balances

        for currency, data_str in raw_wallet.items():
            try:
                data = orjson.loads(data_str)
                balances.append(
                    WalletEntity(
                        user_id=user_id,
                        currency=currency,
                        available=Decimal(str(data.get("available", "0"))),
                        locked=Decimal(str(data.get("locked", "0"))),
                    )
                )
            except Exception as e:
                logger.error(
                    "Failed to parse wallet data for currency %s: %s", currency, e
                )

        return balances

    async def update_wallet_balance(
        self, user_id: str, currency: str, available: Decimal, locked: Decimal
    ):
        wallet_key = f"wallet:{user_id}"
        data = {"available": str(available), "locked": str(locked)}
        await self.redis.hset(wallet_key, currency, orjson.dumps(data))


def get_wallet_repository(redis: Redis = Depends(get_redis)) -> WalletRepository:
    return WalletRepository(redis)

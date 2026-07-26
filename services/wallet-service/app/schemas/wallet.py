from decimal import Decimal

from pydantic import BaseModel


class DepositRequest(BaseModel):
    currency: str
    amount: Decimal


class DepositResponse(BaseModel):
    status: str
    message: str


class WalletBalance(BaseModel):
    currency: str
    available: str
    locked: str


class WalletsResponse(BaseModel):
    balances: list[WalletBalance]

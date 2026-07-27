from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class DepositRequest(BaseModel):
    currency: str = Field(..., min_length=1, max_length=10, pattern=r"^[A-Z0-9_]+$")
    amount: Decimal = Field(..., gt=0)

    @field_validator("currency", mode="before")
    @classmethod
    def strip_and_upper_currency(cls, v):
        if isinstance(v, str):
            return v.strip().upper()
        return v


class DepositResponse(BaseModel):
    status: str
    message: str
    command_id: str


class WalletBalance(BaseModel):
    currency: str = Field(..., min_length=1)
    available: str
    locked: str

    @field_validator("available", "locked")
    @classmethod
    def validate_decimal_string(cls, v):
        try:
            val = Decimal(v)
        except Exception as e:
            raise ValueError(f"invalid balance string: {v}") from e
        if val < Decimal("0"):
            raise ValueError("balance cannot be negative")
        return str(val)


class WalletsResponse(BaseModel):
    balances: list[WalletBalance]

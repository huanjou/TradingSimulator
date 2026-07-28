import enum
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SideChoice(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderTypeChoice(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatusChoice(str, enum.Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELED = "CANCELED"


class OrderBase(BaseModel):
    symbol: str = Field(
        ..., pattern=r"^[A-Z0-9]+/[A-Z0-9]+$", max_length=20, examples=["BTC/USD"]
    )
    side: SideChoice
    order_type: OrderTypeChoice
    quantity: Decimal = Field(..., gt=0, description="Amount to buy or sell")
    price: Decimal | None = Field(
        None,
        gt=0,
        description="Price is required for LIMIT orders, optional for MARKET",
    )


class OrderCreate(OrderBase):
    @model_validator(mode="after")
    def validate_limit_order_price(self) -> "OrderCreate":
        if self.order_type == OrderTypeChoice.LIMIT and self.price is None:
            raise ValueError("Limit orders must have a specified price.")
        return self


class OrderResponse(OrderBase):
    id: uuid.UUID
    user_id: uuid.UUID
    status: OrderStatusChoice
    average_fill_price: float | None = None

    model_config = ConfigDict(from_attributes=True)


class TradeResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    symbol: str
    price: float
    quantity: float
    timestamp: str

    model_config = ConfigDict(from_attributes=True)

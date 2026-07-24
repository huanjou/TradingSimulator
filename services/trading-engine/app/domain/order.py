from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"


class Order(BaseModel):
    id: str
    user_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    average_fill_price: Decimal | None = None
    filled_quantity: Decimal = Field(default=Decimal("0.0"))
    status: OrderStatus = Field(default=OrderStatus.PENDING)

    model_config = ConfigDict(
        frozen=False
    )  # allow modification of quantity for partial fills

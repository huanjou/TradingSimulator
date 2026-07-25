import time
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from .order import OrderStatus


class TradeEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    user_id: str
    symbol: str
    price: Decimal
    quantity: Decimal
    timestamp: float = Field(default_factory=time.time)


class OrderUpdateEvent(BaseModel):
    order_id: str
    user_id: str
    status: OrderStatus
    filled_quantity: Decimal
    average_fill_price: Decimal | None = None

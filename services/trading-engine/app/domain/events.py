from pydantic import BaseModel, Field
from decimal import Decimal
from .order import OrderStatus
import time
import uuid


class TradeEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    symbol: str
    price: Decimal
    quantity: Decimal
    timestamp: float = Field(default_factory=time.time)


class OrderUpdateEvent(BaseModel):
    order_id: str
    status: OrderStatus
    filled_quantity: Decimal

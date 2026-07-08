from pydantic import BaseModel, Field
from decimal import Decimal
from .order import OrderStatus

import uuid

class TradeEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    maker_order_id: str
    taker_order_id: str
    price: Decimal
    quantity: Decimal

class OrderUpdateEvent(BaseModel):
    order_id: str
    status: OrderStatus
    filled_quantity: Decimal

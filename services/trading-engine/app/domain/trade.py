import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class Trade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    maker_order_id: str
    taker_order_id: str
    price: Decimal
    quantity: Decimal

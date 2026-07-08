from datetime import datetime

from pydantic import BaseModel


class OrderEntity(BaseModel):
    id: str
    user_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    filled_quantity: float = 0.0
    status: str
    price: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

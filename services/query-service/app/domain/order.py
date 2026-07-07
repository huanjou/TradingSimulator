from pydantic import BaseModel


class OrderEntity(BaseModel):
    id: str
    user_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    status: str
    price: float | None = None

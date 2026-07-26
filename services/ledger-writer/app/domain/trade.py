from pydantic import BaseModel


class TradeEntity(BaseModel):
    id: str
    order_id: str
    symbol: str
    price: float
    quantity: float
    timestamp: float

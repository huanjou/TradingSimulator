from typing import Optional

from pydantic import BaseModel


class MarketEvent(BaseModel):
    symbol: str
    bid_price: float
    ask_price: float
    timestamp: Optional[int] = None

from enum import Enum
from pydantic import BaseModel, ConfigDict
from decimal import Decimal

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class Order(BaseModel):
    id: str
    user_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    price: Decimal
    quantity: Decimal
    
    model_config = ConfigDict(frozen=False) # allow modification of quantity for partial fills

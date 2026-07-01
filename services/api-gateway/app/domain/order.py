from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import uuid

from app.models.order import SideChoice, OrderTypeChoice, OrderStatusChoice

@dataclass
class OrderEntity:
    id: uuid.UUID
    user_id: uuid.UUID
    symbol: str
    side: SideChoice
    order_type: OrderTypeChoice
    quantity: float
    status: OrderStatusChoice
    price: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        # Enforce Domain Invariants (Business Rules)
        if self.quantity <= 0:
            raise ValueError("Order quantity must be strictly greater than zero.")
        
        if self.order_type == OrderTypeChoice.LIMIT and self.price is None:
            raise ValueError("Limit orders must have a specified price.")
            
        if self.price is not None and self.price <= 0:
            raise ValueError("Order price must be strictly greater than zero.")

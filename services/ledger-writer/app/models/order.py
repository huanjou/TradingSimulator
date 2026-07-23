import enum
import uuid

from app.db.base_class import Base
from sqlalchemy import Column, DateTime, Enum, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func


class SideChoice(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderTypeChoice(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatusChoice(str, enum.Enum):
    PENDING = "PENDING"
    CANCELED = "CANCELED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)

    symbol = Column(String, nullable=False, index=True)
    side = Column(Enum(SideChoice), nullable=False)
    order_type = Column(Enum(OrderTypeChoice), nullable=False)
    quantity = Column(Float, nullable=False)
    filled_quantity = Column(Float, nullable=False, default=0.0)
    price = Column(Float, nullable=True)  # Optional for MARKET orders

    status = Column(
        Enum(OrderStatusChoice), default=OrderStatusChoice.PENDING, nullable=False
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

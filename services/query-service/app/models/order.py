import enum
import uuid

from app.db.base_class import Base
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
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
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    symbol = Column(String, nullable=False, index=True)
    side = Column(Enum(SideChoice), nullable=False)
    order_type = Column(Enum(OrderTypeChoice), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=True)  # Optional for MARKET orders

    status = Column(
        Enum(OrderStatusChoice), default=OrderStatusChoice.PENDING, nullable=False
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="orders")

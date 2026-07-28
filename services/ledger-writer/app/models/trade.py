import uuid

from app.db.base import Base
from sqlalchemy import Column, Float, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID


class Trade(Base):
    __tablename__ = "trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    symbol = Column(String, nullable=False)
    price = Column(Numeric, nullable=False)
    quantity = Column(Numeric, nullable=False)
    timestamp = Column(Float, nullable=False)

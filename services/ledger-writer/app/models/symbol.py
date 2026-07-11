from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.sql import func

from app.db.base_class import Base


class Symbol(Base):
    __tablename__ = "symbols"

    name = Column(String, primary_key=True, index=True)  # e.g. "BTC/USD"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

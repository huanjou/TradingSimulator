import uuid
from decimal import Decimal

from app.db.base_class import Base
from sqlalchemy import Column, Numeric, String, UniqueConstraint


class Balance(Base):
    __tablename__ = "balances"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    currency = Column(String, index=True, nullable=False)
    available = Column(Numeric, nullable=False, default=Decimal("0"))
    locked = Column(Numeric, nullable=False, default=Decimal("0"))

    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uix_user_currency"),
    )

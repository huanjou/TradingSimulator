# Import all the models, so that Base has them before being
# imported by Alembic
from app.db.base_class import Base  # noqa: F401
from app.models.order import Order  # noqa: F401

import uuid

import factory
from app.models.order import Order, OrderStatusChoice, OrderTypeChoice, SideChoice
from app.models.user import User

from .base import AsyncSQLAlchemyFactory


class UserFactory(AsyncSQLAlchemyFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = None  # We handle saving in create_async

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    hashed_password = "fakehashedpassword"
    is_active = True
    is_superuser = False


class OrderFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Order
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    symbol = factory.Iterator(["AAPL", "GOOGL", "MSFT", "TSLA"])
    side = factory.Iterator([SideChoice.BUY, SideChoice.SELL])
    order_type = factory.Iterator([OrderTypeChoice.LIMIT, OrderTypeChoice.MARKET])
    quantity = factory.Faker("pyfloat", positive=True, min_value=1, max_value=100)
    price = factory.Faker("pyfloat", positive=True, min_value=50, max_value=500)
    status = OrderStatusChoice.PENDING


class OrderMessageFactory(factory.DictFactory):
    """
    Generates a dictionary payload representing an incoming Kafka message for an order.
    """

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    user_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    symbol = "BTC/USD"
    side = "BUY"
    type = "LIMIT"
    quantity = "0.5"
    price = "60000.0"
    status = "PENDING"

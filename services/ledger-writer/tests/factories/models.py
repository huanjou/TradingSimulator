import uuid

import factory
from app.models.order import Order, OrderStatusChoice, OrderTypeChoice, SideChoice
from app.models.trade import Trade

from .base import AsyncSQLAlchemyFactory


class OrderFactory(AsyncSQLAlchemyFactory):
    class Meta:
        model = Order
        sqlalchemy_session_persistence = None

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    symbol = "BTC/USD"
    side = SideChoice.BUY
    order_type = OrderTypeChoice.LIMIT
    quantity = 1.0
    price = 50000.0
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


class TradeFactory(AsyncSQLAlchemyFactory):
    class Meta:
        model = Trade
        sqlalchemy_session_persistence = None

    id = factory.LazyFunction(uuid.uuid4)
    order_id = factory.LazyFunction(uuid.uuid4)
    symbol = "BTC/USD"
    price = 50000.0
    quantity = 0.1
    timestamp = 1600000000.0


class TradeMessageFactory(factory.DictFactory):
    """
    Generates a dictionary payload representing an incoming Kafka message for a trade.
    """

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    order_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    symbol = "BTC/USD"
    price = "50000.0"
    quantity = "0.1"
    timestamp = "1600000000.0"

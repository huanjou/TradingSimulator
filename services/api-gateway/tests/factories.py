import uuid
import factory
from app.models.user import User
from app.models.order import Order

class UserFactory(factory.Factory):
    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.LazyAttribute(lambda o: f"test_{uuid.uuid4()}@example.com")
    hashed_password = "fake_password"
    is_active = True
    is_superuser = False


class OrderFactory(factory.Factory):
    class Meta:
        model = Order

    id = factory.LazyFunction(uuid.uuid4)
    # user_id needs to be explicitly passed or we need a SubFactory,
    # but since SQLAlchemy relationships are async, we will just set a dummy UUID
    # or rely on the caller to provide it.
    user_id = factory.LazyFunction(uuid.uuid4)
    symbol = "BTC/USD"
    side = "BUY"
    order_type = "LIMIT"
    quantity = 1.0
    price = 50000.0
    status = "PENDING"

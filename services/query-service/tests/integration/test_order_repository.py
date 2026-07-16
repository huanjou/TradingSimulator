import pytest
from app.models.order import OrderStatusChoice
from app.repositories.order import OrderRepository

from tests.factories.models import OrderFactory, UserFactory


@pytest.mark.asyncio
async def test_order_repository_get_by_id_found(db_session):
    repo = OrderRepository(db_session)

    # Insert user
    user = UserFactory.build()
    db_session.add(user)
    await db_session.flush()

    # Insert order
    order = OrderFactory.build(user_id=user.id, status=OrderStatusChoice.PENDING)
    db_session.add(order)
    await db_session.flush()

    # Query order
    result = await repo.get_by_id(str(order.id))

    assert result is not None
    assert result.id == str(order.id)
    assert result.status == "PENDING"
    assert result.symbol == order.symbol


@pytest.mark.asyncio
async def test_order_repository_get_by_id_not_found(db_session):
    repo = OrderRepository(db_session)

    result = await repo.get_by_id("00000000-0000-0000-0000-000000000000")

    assert result is None

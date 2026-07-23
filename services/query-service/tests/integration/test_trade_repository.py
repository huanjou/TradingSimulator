import uuid

import pytest
from app.models.trade import Trade
from app.repositories.trade import trade_repo

from tests.factories.models import OrderFactory, UserFactory


@pytest.mark.asyncio
async def test_trade_repository_pagination(db_session):
    # Insert user
    user = UserFactory.build()
    db_session.add(user)
    await db_session.flush()

    # Insert order
    order = OrderFactory.build(user_id=user.id)
    db_session.add(order)
    await db_session.flush()

    # Insert 15 trades for the order
    trades = []
    for i in range(15):
        t = Trade(
            id=str(uuid.uuid4()),
            order_id=str(order.id),
            symbol=order.symbol,
            price=50000.0 + i,
            quantity=0.1,
            timestamp=1600000000.0 + i,
        )
        trades.append(t)

    db_session.add_all(trades)
    await db_session.flush()

    # Test limit only
    result1 = await trade_repo.get_by_order_id(db_session, str(order.id), limit=10)
    assert len(result1) == 10

    # Test offset and limit
    result2 = await trade_repo.get_by_order_id(
        db_session, str(order.id), limit=10, offset=10
    )
    assert len(result2) == 5

    # Ensure ordering is descending by timestamp
    assert result1[0].timestamp > result1[-1].timestamp

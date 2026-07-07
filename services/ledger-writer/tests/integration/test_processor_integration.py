import json
import uuid

import pytest
from sqlalchemy import select

from app.models.order import Order
from app.models.user import User
from app.services.processor import process_orders


class MockMessage:
    def __init__(self, value_dict):
        self.value = json.dumps(value_dict).encode("utf-8")


@pytest.mark.asyncio
async def test_process_orders_integration_success(db_session):
    """
    Integration test connecting to the real DB and Redis.
    Writes an order and verifies it exists in the database.
    """
    # Generate unique IDs for the test
    test_user_id = str(uuid.uuid4())
    test_order_id = str(uuid.uuid4())

    messages = [
        MockMessage(
            {
                "id": test_order_id,
                "user_id": test_user_id,
                "symbol": "BTC/USD",
                "side": "BUY",
                "type": "LIMIT",
                "quantity": "0.5",
                "price": "60000",
                "status": "PENDING",
            }
        )
    ]

    # 1. Execute the processor
    await process_orders(messages)

    # 2. Verify against the real database using the same session
    # Check User
    result_user = await db_session.execute(select(User).where(User.id == test_user_id))
    user_in_db = result_user.scalars().first()
    assert user_in_db is not None
    assert str(user_in_db.id) == test_user_id

    # Check Order
    result_order = await db_session.execute(
        select(Order).where(Order.id == test_order_id)
    )
    order_in_db = result_order.scalars().first()
    assert order_in_db is not None
    assert str(order_in_db.id) == test_order_id
    assert order_in_db.symbol == "BTC/USD"
    assert order_in_db.quantity == 0.5
    assert order_in_db.price == 60000.0

    # No manual cleanup needed because db_session will rollback at the end of the test!

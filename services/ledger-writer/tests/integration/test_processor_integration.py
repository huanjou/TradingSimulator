import json

import pytest
from app.models.order import Order
from app.repositories.order import order_repo
from app.repositories.symbol import symbol_repo
from app.repositories.trade import trade_repo
from app.services.processor import process_orders
from sqlalchemy import select

from tests.factories.models import OrderMessageFactory


class MockMessage:
    def __init__(self, value_dict):
        self.value = json.dumps(value_dict).encode("utf-8")


@pytest.mark.asyncio
async def test_process_orders_integration_success(db_session):
    """
    Integration test connecting to the real DB and Redis.
    Writes an order and verifies it exists in the database.
    """
    # Use the factory to generate a payload
    payload = OrderMessageFactory()
    test_user_id = payload["user_id"]
    test_order_id = payload["id"]

    messages = [MockMessage(payload)]

    # 1. Execute the processor
    await process_orders(
        messages,
        session=db_session,
        order_repo=order_repo,
        trade_repo=trade_repo,
        symbol_repo=symbol_repo,
    )

    # 2. Verify against the real database using the same session
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


@pytest.mark.asyncio
async def test_process_orders_idempotency(db_session):
    """
    Test that sending the same order twice does not result in duplicate DB entries
    or crash.
    """
    payload = OrderMessageFactory()
    test_order_id = payload["id"]
    msg = MockMessage(payload)

    # Execute processor twice with the same message
    await process_orders(
        [msg, msg],
        session=db_session,
        order_repo=order_repo,
        trade_repo=trade_repo,
        symbol_repo=symbol_repo,
    )

    # Verify only one order exists
    result_order = await db_session.execute(
        select(Order).where(Order.id == test_order_id)
    )
    orders = result_order.scalars().all()
    assert len(orders) == 1
    assert str(orders[0].id) == test_order_id


@pytest.mark.asyncio
async def test_process_orders_poison_pill(db_session):
    """
    Test that an invalid JSON payload does not crash the processor,
    and valid messages in the same batch are still processed.
    """
    valid_payload = OrderMessageFactory()
    valid_msg = MockMessage(valid_payload)

    class PoisonMessage:
        value = b"NOT VALID JSON {"

    # Batch with poison pill first, then valid message
    messages = [PoisonMessage(), valid_msg]

    await process_orders(
        messages,
        session=db_session,
        order_repo=order_repo,
        trade_repo=trade_repo,
        symbol_repo=symbol_repo,
    )

    # Verify the valid message was processed
    result_order = await db_session.execute(
        select(Order).where(Order.id == valid_payload["id"])
    )
    order_in_db = result_order.scalars().first()
    assert order_in_db is not None
    assert str(order_in_db.id) == valid_payload["id"]


@pytest.mark.asyncio
async def test_process_orders_batch_insertion(db_session):
    """
    Test that a batch of multiple valid orders is correctly inserted into the DB.
    """
    payloads = [OrderMessageFactory() for _ in range(5)]
    messages = [MockMessage(p) for p in payloads]

    await process_orders(
        messages,
        session=db_session,
        order_repo=order_repo,
        trade_repo=trade_repo,
        symbol_repo=symbol_repo,
    )

    # Verify all orders were inserted
    for p in payloads:
        result_order = await db_session.execute(
            select(Order).where(Order.id == p["id"])
        )
        assert result_order.scalars().first() is not None

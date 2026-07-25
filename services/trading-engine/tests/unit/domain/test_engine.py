from decimal import Decimal

import pytest
from app.domain.engine import MatchingEngine
from app.domain.order import Order, OrderSide, OrderStatus, OrderType


@pytest.fixture
def engine():
    return MatchingEngine()


def test_process_market_order_no_price(engine):
    order = Order(
        id="order1",
        user_id="u1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.5"),
    )
    trades, updates = engine.process_order(order)

    assert len(trades) == 0
    assert len(updates) == 1
    assert updates[0].status == OrderStatus.CANCELED


def test_process_market_order_with_price(engine):
    engine.process_market_data("BTCUSDT", Decimal("50000"), Decimal("50010"))

    order = Order(
        id="order2",
        user_id="u1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.5"),
    )
    trades, updates = engine.process_order(order)

    assert len(trades) == 1
    assert trades[0].price == Decimal("50010")  # BUY at ASK
    assert trades[0].quantity == Decimal("1.5")
    assert trades[0].order_id == "order2"

    assert len(updates) == 1
    assert updates[0].status == OrderStatus.FILLED
    assert updates[0].filled_quantity == Decimal("1.5")
    assert updates[0].average_fill_price == Decimal("50010")
    assert order.average_fill_price == Decimal("50010")


def test_process_limit_order_no_cross(engine):
    engine.process_market_data("BTCUSDT", Decimal("50000"), Decimal("50010"))

    order = Order(
        id="order3",
        user_id="u1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("49000"),
        quantity=Decimal("1.0"),
    )
    trades, updates = engine.process_order(order)

    assert len(trades) == 0
    assert len(updates) == 1
    assert updates[0].status == OrderStatus.PENDING

    # Check that it's pending in bids (Max-Heap)
    assert len(engine.bids["BTCUSDT"]) == 1


def test_process_limit_order_cross_immediate(engine):
    engine.process_market_data("BTCUSDT", Decimal("50000"), Decimal("50010"))

    order = Order(
        id="order4",
        user_id="u1",
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        price=Decimal("49000"),  # Selling lower than Bid (crosses)
        quantity=Decimal("1.0"),
    )
    trades, updates = engine.process_order(order)

    assert len(trades) == 1
    assert trades[0].price == Decimal("50000")  # SELL at BID
    assert len(updates) == 1
    assert updates[0].status == OrderStatus.FILLED
    assert updates[0].average_fill_price == Decimal("50000")
    assert order.average_fill_price == Decimal("50000")


def test_process_market_data_fills_pending(engine):
    order = Order(
        id="order5",
        user_id="u1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("50000"),
        quantity=Decimal("1.0"),
    )
    engine.process_order(order)
    assert len(engine.bids["BTCUSDT"]) == 1

    # Price drops to 50000 ask, should fill
    trades, updates = engine.process_market_data(
        "BTCUSDT", Decimal("49990"), Decimal("50000")
    )

    assert len(trades) == 1
    assert trades[0].price == Decimal("50000")
    assert trades[0].order_id == str(order.id)
    assert len(engine.bids["BTCUSDT"]) == 0
    assert updates[0].status == OrderStatus.FILLED
    assert updates[0].average_fill_price == Decimal("50000")
    assert order.average_fill_price == Decimal("50000")


def test_limit_order_fifo_execution(engine):
    """
    Test that limit orders at the same price are executed in FIFO order.
    """
    # Insert 3 BUY orders at the same price
    order_ids = ["o1", "o2", "o3"]
    for oid in order_ids:
        order = Order(
            id=oid,
            user_id="u1",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
        )
        engine.process_order(order)

    assert len(engine.bids["BTCUSDT"]) == 3

    # Market price touches 50000, should fill all 3
    trades, updates = engine.process_market_data(
        "BTCUSDT", Decimal("49990"), Decimal("50000")
    )

    assert len(trades) == 3
    # Check that they were filled in the exact order they were inserted
    assert trades[0].order_id == "o1"
    assert trades[1].order_id == "o2"
    assert trades[2].order_id == "o3"


def test_get_all_pending_orders(engine):
    # Add one buy and one sell order
    buy_order = Order(
        id="buy1",
        user_id="u1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("49000"),
        quantity=Decimal("1.0"),
    )
    sell_order = Order(
        id="sell1",
        user_id="u2",
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        price=Decimal("51000"),
        quantity=Decimal("1.0"),
    )

    engine.process_order(buy_order)
    engine.process_order(sell_order)

    all_orders = engine.get_all_pending_orders()
    assert len(all_orders) == 2
    ids = {order.id for order in all_orders}
    assert "buy1" in ids
    assert "sell1" in ids

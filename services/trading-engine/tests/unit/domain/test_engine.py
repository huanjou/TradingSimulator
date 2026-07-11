import pytest
from decimal import Decimal
from app.domain.engine import MatchingEngine
from app.domain.order import Order, OrderSide, OrderType, OrderStatus


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

    # Check that it's pending
    assert len(engine.pending_orders["BTCUSDT"]) == 1


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
    assert len(engine.pending_orders["BTCUSDT"]) == 1

    # Price drops to 50000 ask, should fill
    trades, updates = engine.process_market_data(
        "BTCUSDT", Decimal("49990"), Decimal("50000")
    )

    assert len(trades) == 1
    assert trades[0].price == Decimal("50000")
    assert trades[0].order_id == str(order.id)
    assert len(engine.pending_orders["BTCUSDT"]) == 0

from app.domain.engine import MatchingEngine
from app.domain.order import OrderSide
from tests.unit.domain.test_order_book import create_order
from decimal import Decimal


def test_engine_routes_orders():
    engine = MatchingEngine()

    # 1. Add order for BTC/USD
    btc_buy = create_order(
        side=OrderSide.BUY, price="50000", quantity="1.0", symbol="BTC/USD"
    )
    trades_1, updates_1 = engine.process_order(btc_buy)

    assert len(trades_1) == 0
    assert len(updates_1) == 1

    # 2. Add order for ETH/USD
    eth_buy = create_order(
        side=OrderSide.BUY, price="3000", quantity="10.0", symbol="ETH/USD"
    )
    trades_2, updates_2 = engine.process_order(eth_buy)

    assert len(trades_2) == 0

    # Verify that engine created two separate order books
    assert "BTC/USD" in engine.order_books
    assert "ETH/USD" in engine.order_books

    assert len(engine.order_books["BTC/USD"].bids) == 1
    assert len(engine.order_books["ETH/USD"].bids) == 1


def test_engine_matches_orders():
    engine = MatchingEngine()

    sell_order = create_order(
        side=OrderSide.SELL,
        price="50000",
        quantity="1.0",
        symbol="BTC/USD",
        user_id="user1",
    )
    engine.process_order(sell_order)

    buy_order = create_order(
        side=OrderSide.BUY,
        price="50000",
        quantity="1.0",
        symbol="BTC/USD",
        user_id="user2",
    )
    trades, updates = engine.process_order(buy_order)

    assert len(trades) == 1
    assert trades[0].symbol == "BTC/USD"
    assert trades[0].price == Decimal("50000")

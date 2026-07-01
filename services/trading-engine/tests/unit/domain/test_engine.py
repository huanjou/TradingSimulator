from app.domain.engine import MatchingEngine
from app.domain.order import OrderSide
from tests.unit.domain.test_order_book import create_order
from decimal import Decimal

def test_engine_routes_orders():
    engine = MatchingEngine()
    
    # 1. Add order for BTC/USD
    btc_buy = create_order(side=OrderSide.BUY, price="50000", quantity="1.0", symbol="BTC/USD")
    trades_1 = engine.process_order(btc_buy)
    
    assert len(trades_1) == 0
    assert "BTC/USD" in engine.order_books
    assert len(engine.order_books["BTC/USD"].bids) == 1
    
    # 2. Add order for ETH/USD
    eth_sell = create_order(side=OrderSide.SELL, price="3000", quantity="10.0", symbol="ETH/USD")
    trades_2 = engine.process_order(eth_sell)
    
    assert len(trades_2) == 0
    assert "ETH/USD" in engine.order_books
    assert len(engine.order_books["ETH/USD"].asks) == 1
    
    # Order books are isolated
    assert len(engine.order_books["BTC/USD"].asks) == 0

def test_engine_matches_orders():
    engine = MatchingEngine()
    
    sell_order = create_order(side=OrderSide.SELL, price="50000", quantity="1.0", symbol="BTC/USD", user_id="user1")
    engine.process_order(sell_order)
    
    buy_order = create_order(side=OrderSide.BUY, price="50000", quantity="1.0", symbol="BTC/USD", user_id="user2")
    trades = engine.process_order(buy_order)
    
    assert len(trades) == 1
    assert trades[0].symbol == "BTC/USD"
    assert trades[0].price == Decimal("50000")

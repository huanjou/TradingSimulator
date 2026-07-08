import pytest
from decimal import Decimal
from app.domain.order import Order, OrderSide, OrderType, OrderStatus
from app.domain.engine import MatchingEngine
from app.domain.events import TradeEvent, OrderUpdateEvent

def create_order(order_id: str, side: OrderSide, type_: OrderType, quantity: str, price: str = None) -> Order:
    return Order(
        id=order_id,
        user_id="user1",
        symbol="BTC_USD",
        side=side,
        order_type=type_,
        quantity=Decimal(quantity),
        price=Decimal(price) if price else None
    )

def test_basic_limit_matching():
    engine = MatchingEngine()

    # 1. Add maker sell order
    sell_order = create_order("sell_1", OrderSide.SELL, OrderType.LIMIT, "2.0", "50000.0")
    trades, updates = engine.process_order(sell_order)

    assert len(trades) == 0
    assert len(updates) == 1
    assert updates[0].status == OrderStatus.PENDING

    # 2. Add taker buy order that fully matches
    buy_order = create_order("buy_1", OrderSide.BUY, OrderType.LIMIT, "2.0", "50000.0")
    trades, updates = engine.process_order(buy_order)

    assert len(trades) == 1
    assert trades[0].maker_order_id == "sell_1"
    assert trades[0].taker_order_id == "buy_1"
    assert trades[0].price == Decimal("50000.0")
    assert trades[0].quantity == Decimal("2.0")

    # Updates should contain maker update (FILLED) and taker update (FILLED)
    assert len(updates) == 2
    assert any(u.order_id == "sell_1" and u.status == OrderStatus.FILLED for u in updates)
    assert any(u.order_id == "buy_1" and u.status == OrderStatus.FILLED for u in updates)

def test_partial_fill():
    engine = MatchingEngine()

    # 1. Maker sells 10 at 50,000
    sell_order = create_order("sell_1", OrderSide.SELL, OrderType.LIMIT, "10.0", "50000.0")
    engine.process_order(sell_order)

    # 2. Taker buys 4 at 50,000
    buy_order = create_order("buy_1", OrderSide.BUY, OrderType.LIMIT, "4.0", "50000.0")
    trades, updates = engine.process_order(buy_order)

    assert len(trades) == 1
    assert trades[0].quantity == Decimal("4.0")

    # Taker should be FILLED, Maker should be PARTIALLY_FILLED
    maker_update = next(u for u in updates if u.order_id == "sell_1")
    taker_update = next(u for u in updates if u.order_id == "buy_1")

    assert maker_update.status == OrderStatus.PARTIALLY_FILLED
    assert maker_update.filled_quantity == Decimal("4.0")

    assert taker_update.status == OrderStatus.FILLED
    assert taker_update.filled_quantity == Decimal("4.0")

    # 3. Another taker buys 8 at 50,000
    # There are only 6 left in the maker order
    buy_order_2 = create_order("buy_2", OrderSide.BUY, OrderType.LIMIT, "8.0", "50000.0")
    trades, updates = engine.process_order(buy_order_2)

    assert len(trades) == 1
    assert trades[0].quantity == Decimal("6.0") # Takes remaining 6

    maker_update = next(u for u in updates if u.order_id == "sell_1")
    taker_update = next(u for u in updates if u.order_id == "buy_2")

    assert maker_update.status == OrderStatus.FILLED
    assert maker_update.filled_quantity == Decimal("10.0")

    assert taker_update.status == OrderStatus.PARTIALLY_FILLED
    assert taker_update.filled_quantity == Decimal("6.0")

def test_market_order_matching():
    engine = MatchingEngine()

    # Maker sells 2 @ 100, 2 @ 200
    engine.process_order(create_order("sell_1", OrderSide.SELL, OrderType.LIMIT, "2.0", "100.0"))
    engine.process_order(create_order("sell_2", OrderSide.SELL, OrderType.LIMIT, "2.0", "200.0"))

    # Market buy for 5
    market_buy = create_order("buy_mkt", OrderSide.BUY, OrderType.MARKET, "5.0")
    trades, updates = engine.process_order(market_buy)

    # Should trade 2 @ 100, 2 @ 200, and cancel remaining 1
    assert len(trades) == 2
    assert trades[0].price == Decimal("100.0")
    assert trades[0].quantity == Decimal("2.0")
    assert trades[1].price == Decimal("200.0")
    assert trades[1].quantity == Decimal("2.0")

    taker_update = next(u for u in updates if u.order_id == "buy_mkt" and u.status in [OrderStatus.CANCELED, OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED])

    # The order was not fully filled, so the remainder was canceled.
    assert taker_update.status == OrderStatus.CANCELED
    assert taker_update.filled_quantity == Decimal("4.0")

def test_time_priority():
    engine = MatchingEngine()

    # Two makers selling at the same price
    engine.process_order(create_order("sell_early", OrderSide.SELL, OrderType.LIMIT, "2.0", "100.0"))
    engine.process_order(create_order("sell_late", OrderSide.SELL, OrderType.LIMIT, "2.0", "100.0"))

    # Taker buys 1
    buy = create_order("buy", OrderSide.BUY, OrderType.LIMIT, "1.0", "100.0")
    trades, _ = engine.process_order(buy)

    assert len(trades) == 1
    assert trades[0].maker_order_id == "sell_early" # Should match with the older one first

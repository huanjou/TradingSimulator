import pytest
from uuid import uuid4
from decimal import Decimal
from typing import List

from app.domain.order import Order, OrderSide, OrderType
from app.domain.order_book import OrderBook
from app.domain.trade import Trade


def create_order(
    side: OrderSide, 
    price: str, 
    quantity: str, 
    user_id: str = "user1", 
    symbol: str = "BTC/USD"
) -> Order:
    return Order(
        id=str(uuid4()),
        user_id=user_id,
        symbol=symbol,
        side=side,
        order_type=OrderType.LIMIT,
        price=Decimal(price),
        quantity=Decimal(quantity),
    )


def test_add_order_no_match():
    book = OrderBook(symbol="BTC/USD")
    
    buy_order = create_order(side=OrderSide.BUY, price="50000", quantity="1.0")
    trades, updates = book.add_order(buy_order)
    
    assert len(trades) == 0
    assert len(book.bids) == 1
    assert len(book.asks) == 0


def test_exact_match():
    book = OrderBook(symbol="BTC/USD")
    
    # 1. User 1 places a sell order (Ask)
    sell_order = create_order(side=OrderSide.SELL, price="50000", quantity="1.0", user_id="user1")
    trades_1, updates_1 = book.add_order(sell_order)
    assert len(trades_1) == 0
    
    # 2. User 2 places a buy order (Bid) matching exactly
    buy_order = create_order(side=OrderSide.BUY, price="50000", quantity="1.0", user_id="user2")
    trades_2, updates_2 = book.add_order(buy_order)
    
    # Assert Trade is generated
    assert len(trades_2) == 1
    trade = trades_2[0]
    assert trade.maker_order_id == sell_order.id
    assert trade.taker_order_id == buy_order.id
    assert trade.price == Decimal("50000")
    assert trade.quantity == Decimal("1.0")
    
    # Assert Order Book is empty again
    assert len(book.bids) == 0
    assert len(book.asks) == 0


def test_partial_match():
    book = OrderBook(symbol="BTC/USD")
    
    # Sell 2.0 BTC @ 50000
    sell_order = create_order(side=OrderSide.SELL, price="50000", quantity="2.0", user_id="user1")
    book.add_order(sell_order)
    
    # Buy 0.5 BTC @ 50000
    buy_order = create_order(side=OrderSide.BUY, price="50000", quantity="0.5", user_id="user2")
    trades, updates = book.add_order(buy_order)
    
    assert len(trades) == 1
    assert trades[0].quantity == Decimal("0.5")
    
    # Verify remaining order book state
    assert len(book.asks) == 1
    assert book.asks[0].quantity - book.asks[0].filled_quantity == Decimal("1.5") # 2.0 - 0.5
    assert len(book.bids) == 0


def test_price_time_priority():
    book = OrderBook(symbol="BTC/USD")
    
    # 1. Ask 1: 1.0 @ 51000
    ask1 = create_order(side=OrderSide.SELL, price="51000", quantity="1.0")
    book.add_order(ask1)
    
    # 2. Ask 2: 1.0 @ 50000 (Better price, should be matched first)
    ask2 = create_order(side=OrderSide.SELL, price="50000", quantity="1.0")
    book.add_order(ask2)
    
    # 3. Ask 3: 1.0 @ 50000 (Same price as Ask 2, but arrived later)
    ask3 = create_order(side=OrderSide.SELL, price="50000", quantity="1.0")
    book.add_order(ask3)
    
    # Taker buys 1.5 BTC @ 51000
    buy_order = create_order(side=OrderSide.BUY, price="51000", quantity="1.5")
    trades, updates = book.add_order(buy_order)
    
    assert len(trades) == 2
    
    # First trade should be with Ask 2 (best price)
    assert trades[0].maker_order_id == ask2.id
    assert trades[0].price == Decimal("50000")
    assert trades[0].quantity == Decimal("1.0")
    
    # Second trade should be with Ask 3 (time priority over Ask 1, same price as Ask 2)
    assert trades[1].maker_order_id == ask3.id
    assert trades[1].price == Decimal("50000")
    assert trades[1].quantity == Decimal("0.5")
    
    # Remaining book:
    assert len(book.bids) == 0
    assert len(book.asks) == 2
    # Ask 3 has 0.5 left
    assert book.asks[0].id == ask3.id
    assert book.asks[0].quantity - book.asks[0].filled_quantity == Decimal("0.5")
    # Ask 1 is untouched
    assert book.asks[1].id == ask1.id
    assert book.asks[1].quantity == Decimal("1.0")

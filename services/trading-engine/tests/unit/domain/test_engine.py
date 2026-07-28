from decimal import Decimal

import pytest
from app.domain.engine import MatchingEngine, WalletInfo
from app.domain.order import Order, OrderSide, OrderStatus, OrderType


@pytest.fixture
def engine():
    e = MatchingEngine()
    e.wallets["u1"] = {
        "BTC": WalletInfo(available=Decimal("1000000"), locked=Decimal("0")),
        "USD": WalletInfo(available=Decimal("1000000"), locked=Decimal("0")),
        "USDT": WalletInfo(available=Decimal("1000000"), locked=Decimal("0")),
    }
    e.wallets["u2"] = {
        "BTC": WalletInfo(available=Decimal("1000000"), locked=Decimal("0")),
        "USD": WalletInfo(available=Decimal("1000000"), locked=Decimal("0")),
        "USDT": WalletInfo(available=Decimal("1000000"), locked=Decimal("0")),
    }
    return e


def test_process_market_order_no_price(engine):
    order = Order(
        id="order1",
        user_id="u1",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.5"),
    )
    trades, updates, wallet_updates = engine.process_order(order)

    assert len(trades) == 0
    assert len(updates) == 1
    assert updates[0].status == OrderStatus.CANCELED


def test_process_market_order_with_price(engine):
    engine.process_market_data("BTC/USDT", Decimal("50000"), Decimal("50010"))

    order = Order(
        id="order2",
        user_id="u1",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.5"),
    )
    trades, updates, wallet_updates = engine.process_order(order)

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
    engine.process_market_data("BTC/USDT", Decimal("50000"), Decimal("50010"))

    order = Order(
        id="order3",
        user_id="u1",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("49000"),
        quantity=Decimal("1.0"),
    )
    trades, updates, wallet_updates = engine.process_order(order)

    assert len(trades) == 0
    assert len(updates) == 1
    assert updates[0].status == OrderStatus.PENDING

    # Check that it's pending in bids (Max-Heap)
    assert len(engine.bids["BTC/USDT"]) == 1


def test_process_limit_order_cross_immediate(engine):
    engine.process_market_data("BTC/USDT", Decimal("50000"), Decimal("50010"))

    order = Order(
        id="order4",
        user_id="u1",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        price=Decimal("49000"),  # Selling lower than Bid (crosses)
        quantity=Decimal("1.0"),
    )
    trades, updates, wallet_updates = engine.process_order(order)

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
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("50000"),
        quantity=Decimal("1.0"),
    )
    engine.process_order(order)
    assert len(engine.bids["BTC/USDT"]) == 1

    # Price drops to 50000 ask, should fill
    trades, updates, wallet_updates = engine.process_market_data(
        "BTC/USDT", Decimal("49990"), Decimal("50000")
    )

    assert len(trades) == 1
    assert trades[0].price == Decimal("50000")
    assert trades[0].order_id == str(order.id)
    assert len(engine.bids["BTC/USDT"]) == 0
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
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
        )
        engine.process_order(order)

    assert len(engine.bids["BTC/USDT"]) == 3

    # Market price touches 50000, should fill all 3
    trades, updates, wallet_updates = engine.process_market_data(
        "BTC/USDT", Decimal("49990"), Decimal("50000")
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
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("49000"),
        quantity=Decimal("1.0"),
    )
    sell_order = Order(
        id="sell1",
        user_id="u2",
        symbol="BTC/USDT",
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


def test_process_market_order_rejected_no_balance(engine):
    engine.process_market_data("BTC/USD", Decimal("50000"), Decimal("50010"))
    order = Order(
        id="order_no_bal",
        user_id="u1",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.0"),
    )
    # User has no balance
    engine.wallets["u1"] = {}
    trades, updates, wallet_updates = engine.process_order(order)

    assert len(trades) == 0
    assert len(updates) == 1
    assert updates[0].status == OrderStatus.REJECTED
    assert len(wallet_updates) == 0


def test_process_limit_order_locked_balance(engine):
    engine.process_market_data("BTC/USD", Decimal("50000"), Decimal("50010"))

    # Give user some balance
    engine.wallets.setdefault("u1", {})["USD"] = WalletInfo(
        available=Decimal("100000"), locked=Decimal("0")
    )

    order = Order(
        id="order_limit_bal",
        user_id="u1",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("49000"),
        quantity=Decimal("1.0"),
    )
    trades, updates, wallet_updates = engine.process_order(order)

    assert len(trades) == 0
    assert len(updates) == 1
    assert updates[0].status == OrderStatus.PENDING

    # 49000 USD should be locked
    assert engine.wallets["u1"]["USD"].available == Decimal("51000")
    assert engine.wallets["u1"]["USD"].locked == Decimal("49000")
    assert len(wallet_updates) == 1
    assert wallet_updates[0].available == Decimal("51000")


def test_process_market_data_fills_pending_deducts_balance(engine):
    engine.wallets["u1"] = {
        "USD": WalletInfo(available=Decimal("100000"), locked=Decimal("0")),
        "BTC": WalletInfo(available=Decimal("0"), locked=Decimal("0")),
    }

    order = Order(
        id="order_fill_bal",
        user_id="u1",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("50000"),
        quantity=Decimal("1.0"),
    )
    engine.process_order(order)
    assert engine.wallets["u1"]["USD"].locked == Decimal("50000")

    trades, updates, wallet_updates = engine.process_market_data(
        "BTC/USD", Decimal("49990"), Decimal("50000")
    )

    assert len(trades) == 1
    assert updates[0].status == OrderStatus.FILLED

    # Lock is removed, balance deducted, BTC added
    assert engine.wallets["u1"]["USD"].locked == Decimal("0")
    assert engine.wallets["u1"]["USD"].available == Decimal("50000")
    assert engine.wallets["u1"]["BTC"].available == Decimal("1.0")

    # It should yield wallet updates for USD and BTC
    assert len(wallet_updates) >= 2


def test_trade_id_is_deterministic_per_order(engine):
    """Re-processing the same order must yield the SAME trade id.

    This is what makes trade projection idempotent on restart: if the engine
    re-matches an order whose offset was committed but not yet snapshotted, the
    ledger dedupes it via on_conflict_do_nothing(trade.id) instead of writing a
    duplicate trade.
    """
    engine.process_market_data("BTC/USDT", Decimal("50000"), Decimal("50010"))
    order = Order(
        id="deterministic-order-1",
        user_id="u1",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.0"),
    )
    trades_a, _, _ = engine.process_order(order)

    # A fresh engine re-processing an identical order (same id) -> same trade id.
    engine_b = MatchingEngine()
    engine_b.wallets["u1"] = {
        "BTC": WalletInfo(available=Decimal("1000000"), locked=Decimal("0")),
        "USDT": WalletInfo(available=Decimal("1000000"), locked=Decimal("0")),
    }
    engine_b.process_market_data("BTC/USDT", Decimal("50000"), Decimal("50010"))
    order_replay = Order(
        id="deterministic-order-1",
        user_id="u1",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.0"),
    )
    trades_b, _, _ = engine_b.process_order(order_replay)

    assert len(trades_a) == 1
    assert len(trades_b) == 1
    assert trades_a[0].id == trades_b[0].id
    # Different orders must not collide.
    assert trades_a[0].id != str(engine._counter)


def test_trade_ids_differ_across_orders(engine):
    engine.process_market_data("BTC/USDT", Decimal("50000"), Decimal("50010"))
    ids = set()
    for i in range(3):
        order = Order(
            id=f"order-{i}",
            user_id="u1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1.0"),
        )
        trades, _, _ = engine.process_order(order)
        ids.add(trades[0].id)
    assert len(ids) == 3

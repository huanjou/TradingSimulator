import random
import time
import uuid
from decimal import Decimal

from app.domain.engine import MatchingEngine
from app.domain.order import Order, OrderSide, OrderStatus, OrderType

SYMBOL = "BTC/USD"
NUM_ORDERS = 100_000
NUM_USERS = 100


def fund_users(engine: MatchingEngine, user_ids: list[str]) -> None:
    """Deposits both legs so no order is rejected for insufficient funds.

    Rejections short-circuit process_order, which would benchmark the
    validation path instead of the matching path.
    """
    for user_id in user_ids:
        engine.process_deposit(user_id, "USD", Decimal("100000000000"))
        engine.process_deposit(user_id, "BTC", Decimal("1000000"))


def run_benchmark():
    print("Initializing MatchingEngine...")
    engine = MatchingEngine()

    user_ids = [str(uuid.uuid4()) for _ in range(NUM_USERS)]
    fund_users(engine, user_ids)

    print(f"Generating {NUM_ORDERS} random orders...")
    orders = []
    for _ in range(NUM_ORDERS):
        is_buy = random.choice([True, False])
        # Random price around 50,000, uniform distribution between 49000 and 51000
        price = Decimal(str(round(random.uniform(49000, 51000), 2)))
        qty = Decimal(str(round(random.uniform(0.01, 2.0), 4)))

        order = Order(
            id=str(uuid.uuid4()),
            user_id=random.choice(user_ids),
            symbol=SYMBOL,
            side=OrderSide.BUY if is_buy else OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=price,
            quantity=qty,
            filled_quantity=Decimal("0.0"),
            status=OrderStatus.PENDING,
        )
        orders.append(order)

    # No market price is known yet, so every LIMIT order locks funds and rests
    # on the book: this measures the order intake path.
    print("Starting core matching benchmark (order intake)...")
    start_time = time.time()

    trades_count = 0
    updates_count = 0
    rejected_count = 0

    for order in orders:
        trades, updates, _wallet_updates = engine.process_order(order)
        trades_count += len(trades)
        updates_count += len(updates)
        rejected_count += sum(
            1 for update in updates if update.status == OrderStatus.REJECTED
        )

    intake_duration = time.time() - start_time
    intake_ops_per_sec = NUM_ORDERS / intake_duration

    resting_bids = len(engine.bids.get(SYMBOL, []))
    resting_asks = len(engine.asks.get(SYMBOL, []))

    # A market tick that crosses the whole book drains both heaps: this
    # measures the matching path.
    print("Starting core matching benchmark (market tick drain)...")
    drain_start = time.time()
    md_trades, md_updates, _md_wallet_updates = engine.process_market_data(
        SYMBOL, bid=Decimal("60000"), ask=Decimal("40000")
    )
    drain_duration = time.time() - drain_start
    drain_ops_per_sec = len(md_trades) / drain_duration if drain_duration else 0.0

    print("\n--- BENCHMARK RESULTS ---")
    print(f"Total Orders Processed: {NUM_ORDERS}")
    print(f"Intake Time: {intake_duration:.4f} seconds")
    print(f"Intake Operations/sec: {intake_ops_per_sec:.2f}")
    print(f"Trades Generated On Intake: {trades_count}")
    print(f"Order Updates Generated On Intake: {updates_count}")
    print(f"Rejected Orders: {rejected_count}")
    print(f"Book Before Market Tick: {resting_bids} Bids, {resting_asks} Asks")
    print(f"Market Tick Drain Time: {drain_duration:.4f} seconds")
    print(f"Market Tick Trades: {len(md_trades)} ({drain_ops_per_sec:.2f} trades/sec)")
    print(f"Market Tick Order Updates: {len(md_updates)}")
    print(
        "Book After Market Tick: "
        f"{len(engine.bids.get(SYMBOL, []))} Bids, "
        f"{len(engine.asks.get(SYMBOL, []))} Asks"
    )
    print("-------------------------\n")


if __name__ == "__main__":
    run_benchmark()

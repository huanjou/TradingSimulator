import random
import time
import uuid
from decimal import Decimal

from app.domain.order import Order, OrderSide, OrderStatus, OrderType
from app.domain.order_book import OrderBook


def run_benchmark():
    print("Initializing OrderBook...")
    book = OrderBook(symbol="BTC/USD")

    num_orders = 100_000
    orders = []

    print(f"Generating {num_orders} random orders...")
    for _ in range(num_orders):
        is_buy = random.choice([True, False])
        # Random price around 50,000, uniform distribution between 49000 and 51000
        price = Decimal(str(round(random.uniform(49000, 51000), 2)))
        qty = Decimal(str(round(random.uniform(0.01, 2.0), 4)))

        order = Order(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            symbol="BTC/USD",
            side=OrderSide.BUY if is_buy else OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=price,
            quantity=qty,
            filled_quantity=Decimal("0.0"),
            status=OrderStatus.PENDING,
        )
        orders.append(order)

    print("Starting core matching benchmark...")
    start_time = time.time()

    trades_count = 0
    updates_count = 0

    for order in orders:
        trades, updates = book.add_order(order)
        trades_count += len(trades)
        updates_count += len(updates)

    end_time = time.time()
    duration = end_time - start_time
    ops_per_sec = num_orders / duration

    print("\n--- BENCHMARK RESULTS ---")
    print(f"Total Orders Processed: {num_orders}")
    print(f"Total Time: {duration:.4f} seconds")
    print(f"Operations/sec: {ops_per_sec:.2f}")
    print(f"Total Trades Generated: {trades_count}")
    print(f"Total Order Updates Generated: {updates_count}")
    print(f"OrderBook State: {len(book.bids)} Bids, {len(book.asks)} Asks")
    print("-------------------------\n")


if __name__ == "__main__":
    run_benchmark()

import asyncio
import json
import random
import time
import uuid

from aiokafka import AIOKafkaProducer
from app.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def run_benchmark():
    settings = get_settings()
    db_url = str(settings.POSTGRES_URL)

    broker = settings.KAFKA_BROKER
    num_orders = 10000

    print(f"Connecting to DB at {db_url}...")
    engine = create_async_engine(db_url)

    # Check initial count
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM orders WHERE status = 'FILLED'")
        )
        initial_count = result.scalar()

    print(f"Initial order count in DB: {initial_count}")

    print(f"Connecting to Kafka at {broker}...")
    producer = AIOKafkaProducer(
        bootstrap_servers=broker,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()

    messages = []
    print(f"Generating and inserting {num_orders} orders to DB...")

    # Pre-insert orders so they can be updated
    insert_user_query = text(
        "INSERT INTO users (id, email, hashed_password, created_at) VALUES (:id, :email, :hashed_password, now()) ON CONFLICT (id) DO NOTHING"  # noqa: E501
    )
    insert_query = text(
        "INSERT INTO orders (id, user_id, symbol, side, order_type, price, quantity, status, created_at, updated_at) VALUES (:id, :user_id, :symbol, :side, :order_type, :price, :quantity, :status, now(), now())"  # noqa: E501
    )

    mock_user_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            insert_user_query,
            {
                "id": mock_user_id,
                "email": f"benchmark_{mock_user_id}@test.com",
                "hashed_password": "dummy",
            },
        )

        for _ in range(num_orders):
            order_id = str(uuid.uuid4())
            await conn.execute(
                insert_query,
                {
                    "id": order_id,
                    "user_id": mock_user_id,
                    "symbol": "BTC/USD",
                    "side": "BUY",
                    "order_type": "LIMIT",
                    "price": 50000.0,
                    "quantity": 1.0,
                    "status": "PENDING",
                },
            )

            msg = {
                "order_id": order_id,
                "status": "FILLED",
                "filled_quantity": str(round(random.uniform(0.01, 2.0), 4)),
            }
            messages.append((order_id, msg))

    print("Starting Ledger Writer benchmark...")

    produce_start = time.time()
    for _, msg in messages:
        await producer.send_and_wait("order_updates", msg)
    produce_end = time.time()

    print(f"Produced {num_orders} updates in {produce_end - produce_start:.2f}s")

    # Poll DB until count reaches initial_count + num_orders
    target_count = initial_count + num_orders
    current_count = initial_count

    print("Waiting for Ledger Writer to process and write to DB...")
    timeout = 30.0
    start_poll = time.time()

    while current_count < target_count:
        if time.time() - start_poll > timeout:
            print("Timeout waiting for Ledger Writer!")
            break

        await asyncio.sleep(0.5)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM orders WHERE status = 'FILLED'")
            )
            current_count = result.scalar()

    end_time = time.time()
    duration = end_time - produce_start
    ops_per_sec = (current_count - initial_count) / duration

    print("\n--- LEDGER WRITER BENCHMARK RESULTS ---")
    print(f"Total Updates Produced: {num_orders}")
    print(f"Total Written to DB: {current_count - initial_count}")
    print(f"Total Time (Produce + Write): {duration:.4f} seconds")
    print(f"End-to-End Write Throughput: {ops_per_sec:.2f} orders/sec")
    print("---------------------------------------\n")

    await producer.stop()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_benchmark())

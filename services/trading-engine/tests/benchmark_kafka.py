import asyncio
import time
import uuid
import json
import random
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.core.config import settings


async def run_benchmark():
    num_orders = 10000
    broker = settings.KAFKA_BROKER

    print(f"Connecting to Kafka at {broker}...")
    producer = AIOKafkaProducer(
        bootstrap_servers=broker,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    consumer = AIOKafkaConsumer(
        settings.KAFKA_ORDER_UPDATES_TOPIC,
        bootstrap_servers=broker,
        group_id=f"benchmark_group_{uuid.uuid4()}",
        auto_offset_reset="latest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )

    await producer.start()
    await consumer.start()

    # Generate messages
    messages = []
    print(f"Generating {num_orders} orders for Kafka...")
    for _ in range(num_orders):
        order_id = str(uuid.uuid4())
        msg = {
            "id": order_id,
            "user_id": str(uuid.uuid4()),
            "symbol": "BTC/USD",
            "side": random.choice(["BUY", "SELL"]),
            "order_type": "LIMIT",
            "price": str(round(random.uniform(49000, 51000), 2)),
            "quantity": str(round(random.uniform(0.01, 2.0), 4)),
            "status": "PENDING",
        }
        messages.append((order_id, msg))

    print(
        "Starting Kafka benchmark... (Make sure infra and trading-engine are running)"
    )

    # Start consumer task
    updates_received = 0
    start_time = time.time()

    async def consume_updates():
        nonlocal updates_received
        async for msg in consumer:
            update = msg.value
            # For every order, we expect at least 1 update (its final status)
            updates_received += 1
            if updates_received >= num_orders:
                break

    consumer_task = asyncio.create_task(consume_updates())

    # Produce all messages
    produce_start = time.time()
    for order_id, msg in messages:
        await producer.send_and_wait(settings.KAFKA_ORDERS_TOPIC, msg)
    produce_end = time.time()

    print(f"Produced {num_orders} messages in {produce_end - produce_start:.2f}s")

    # Wait for consumer
    try:
        await asyncio.wait_for(consumer_task, timeout=30.0)
    except asyncio.TimeoutError:
        print("Timeout waiting for updates! Received so far:", updates_received)

    end_time = time.time()
    duration = end_time - start_time
    ops_per_sec = num_orders / duration

    print("\n--- KAFKA BENCHMARK RESULTS ---")
    print(f"Total Orders Produced: {num_orders}")
    print(f"Total Updates Received: {updates_received}")
    print(f"Total Time (Produce + Process + Consume): {duration:.4f} seconds")
    print(f"End-to-End Throughput: {ops_per_sec:.2f} orders/sec")
    print("-------------------------------\n")

    await producer.stop()
    await consumer.stop()


if __name__ == "__main__":
    asyncio.run(run_benchmark())

import asyncio
import os
import time
import uuid

import grpc
from app.core.redis import redis_client
from app.db.base_class import Base
from app.grpc_stubs import orders_pb2, orders_pb2_grpc
from app.models.order import Order
from app.models.trade import Trade
from sqlalchemy.ext.asyncio import create_async_engine

original_url = os.environ.get(
    "POSTGRES_URL", "postgresql+asyncpg://admin:password@127.0.0.1:5432/ledger_db"
)
original_url = original_url.replace("postgres-replica", "postgres-primary")
test_db_url = original_url

os.environ["POSTGRES_URL"] = test_db_url
# Use dev redis so cache interacts with running service
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"


async def setup_data(order_id: str):
    engine = create_async_engine(test_db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        # We'll just insert raw SQL to avoid model mismatches
        await conn.execute(
            Order.__table__.insert().values(
                id=order_id,
                user_id="e5c6a157-1959-4d69-beeb-9d9fc6cc1502",
                symbol="BTCUSD",
                side="BUY",
                order_type="MARKET",
                quantity=10.0,
                price=50000.0,
                status="FILLED",
            )
        )
        # Insert 1000 trades
        trades = []
        for i in range(1000):
            trades.append(
                {
                    "id": str(uuid.uuid4()),
                    "order_id": order_id,
                    "symbol": "BTCUSD",
                    "price": 50000.0 + i,
                    "quantity": 0.01,
                    "timestamp": 1600000000.0 + i,
                }
            )
        await conn.execute(Trade.__table__.insert(), trades)

    await engine.dispose()
    print(f"✅ Data setup complete. Order {order_id} with 1000 trades inserted.")

    # Wait for postgres-replica to sync
    print("Waiting 1 second for postgres replication...")
    await asyncio.sleep(1)


async def test_cache_aside(order_id: str, stub: orders_pb2_grpc.OrderQueryServiceStub):
    print("\n--- 🧪 Testing Cache-Aside Pattern ---")
    await redis_client.delete(f"order:{order_id}")
    print("Cache cleared.")

    start_time = time.time()
    req = orders_pb2.GetOrderRequest(order_id=order_id)
    _ = await stub.GetOrder(req)
    t1 = (time.time() - start_time) * 1000
    print(f"1st request (Cache Miss) took: {t1:.2f} ms")

    # Wait for postgres-replica to sync
    await asyncio.sleep(0.5)
    cached = await redis_client.hgetall(f"order:{order_id}")
    assert cached, "Cache was not populated! Cache-Aside failed."
    print("✅ Cache was populated successfully.")

    start_time = time.time()
    _ = await stub.GetOrder(req)
    t2 = (time.time() - start_time) * 1000
    print(f"2nd request (Cache Hit) took: {t2:.2f} ms")

    if t2 < t1:
        print(f"🚀 Cache hit is {t1/t2:.1f}x faster!")
    else:
        print(f"⚠️ Cache hit was not faster. (Hit: {t2:.2f}ms, Miss: {t1:.2f}ms)")


async def test_pagination(order_id: str, stub: orders_pb2_grpc.OrderQueryServiceStub):
    print("\n--- 🧪 Testing gRPC Pagination (OOM Protection) ---")

    req_limit = orders_pb2.GetTradesRequest(order_id=order_id, limit=100, offset=0)
    resp_limit = await stub.GetTrades(req_limit)
    assert (
        len(resp_limit.trades) == 100
    ), f"Expected 100 trades, got {len(resp_limit.trades)}"
    print("✅ Limit=100 returned exactly 100 trades.")

    req_offset = orders_pb2.GetTradesRequest(order_id=order_id, limit=10, offset=100)
    resp_offset = await stub.GetTrades(req_offset)
    assert (
        len(resp_offset.trades) == 10
    ), f"Expected 10 trades, got {len(resp_offset.trades)}"
    print("✅ Offset=100, Limit=10 returned exactly 10 trades.")


async def test_concurrency(order_id: str, stub: orders_pb2_grpc.OrderQueryServiceStub):
    print("\n--- 🧪 Testing Concurrency (100 simultaneous requests) ---")
    req = orders_pb2.GetOrderRequest(order_id=order_id)

    start_time = time.time()
    tasks = [stub.GetOrder(req) for _ in range(100)]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    t = (time.time() - start_time) * 1000

    success = sum(1 for r in responses if not isinstance(r, Exception))
    errors = sum(1 for r in responses if isinstance(r, Exception))

    print(f"Completed in {t:.2f} ms")
    print(f"✅ Success: {success}/100, ❌ Errors: {errors}/100")
    if errors > 0:
        print(f"Sample error: {responses[0]}")


async def main():
    order_id = str(uuid.uuid4())

    try:
        await setup_data(order_id)
    except Exception as e:
        print(f"Failed to setup data, db might not be clean: {e}")

    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = orders_pb2_grpc.OrderQueryServiceStub(channel)

        await test_cache_aside(order_id, stub)
        await test_pagination(order_id, stub)
        await test_concurrency(order_id, stub)


if __name__ == "__main__":
    asyncio.run(main())

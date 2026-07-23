import asyncio
import json
import uuid

import pytest
from aiokafka import AIOKafkaProducer

from app.core.config import get_settings
from app.core.redis import redis_client
from app.services.consumer import consume

settings = get_settings()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_writer_integration(kafka_producer: AIOKafkaProducer):
    """
    Test that the cache-writer consumer reads an order from Kafka
    and successfully writes it to Redis.
    """
    # 1. Generate unique order data
    order_id = f"test-order-{uuid.uuid4().hex}"
    user_id = f"test-user-{uuid.uuid4().hex}"
    order_data = {
        "id": order_id,
        "user_id": user_id,
        "symbol": "ETH/USD",
        "status": "OPEN",
    }

    # 2. Publish order event to Kafka
    await kafka_producer.send_and_wait(
        settings.KAFKA_ORDER_UPDATES_TOPIC,
        value=json.dumps(order_data).encode("utf-8"),
    )

    # 3. Start the consumer loop temporarily
    consumer_task = asyncio.create_task(consume())
    
    # Wait for the consumer to process the message (with retry)
    cached_order = None
    for _ in range(10):
        cached_order = await redis_client.hgetall(f"order:{order_id}")
        if cached_order:
            break
        await asyncio.sleep(1.0)

    # Cancel the consumer loop
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    # 4. Verify data in Redis
    # Check the hash
    assert cached_order, "Order was not saved to Redis"
    assert cached_order.get("id") == order_id
    assert cached_order.get("status") == "OPEN"

    # Check the user index
    user_orders = await redis_client.smembers(f"user:{user_id}:orders")
    assert order_id in user_orders, "Order ID not added to user set"

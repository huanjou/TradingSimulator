import asyncio
import json
import pytest
import uuid
from decimal import Decimal
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.core.config import settings

@pytest.mark.asyncio
async def test_kafka_integration():
    # 1. Start Producer to send mock order
    producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BROKER)
    await producer.start()

    # 2. Start Consumer to read from trades and order_updates
    # We use a unique group_id so we get all messages
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TRADES_TOPIC,
        settings.KAFKA_ORDER_UPDATES_TOPIC,
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id=f"test-group-{uuid.uuid4()}",
        auto_offset_reset="latest" # We only care about messages produced during this test
    )
    await consumer.start()

    try:
        # Create a unique symbol for isolation
        symbol = f"TEST_{uuid.uuid4().hex[:8]}"

        # We will post a SELL limit order and then a BUY market order
        sell_order = {
            "id": str(uuid.uuid4()),
            "user_id": "maker",
            "symbol": symbol,
            "side": "SELL",
            "order_type": "LIMIT",
            "quantity": "5.0",
            "price": "100.0"
        }

        buy_order = {
            "id": str(uuid.uuid4()),
            "user_id": "taker",
            "symbol": symbol,
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "5.0"
        }

        # Publish orders
        await producer.send_and_wait(settings.KAFKA_ORDERS_TOPIC, json.dumps(sell_order).encode("utf-8"))
        await producer.send_and_wait(settings.KAFKA_ORDERS_TOPIC, json.dumps(buy_order).encode("utf-8"))

        # Now listen for the results
        # We expect:
        # 1. OrderUpdate for SELL (PENDING) -> but wait, currently our engine doesn't emit PENDING for first insertion, only after matching. Actually it does emit PENDING.
        # 2. TradeEvent
        # 3. OrderUpdate for SELL (FILLED)
        # 4. OrderUpdate for BUY (FILLED)

        events_received = {
            "trades": 0,
            "updates_sell_filled": False,
            "updates_buy_filled": False
        }

        # Timeout after 5 seconds
        async def wait_for_messages():
            async for msg in consumer:
                payload = json.loads(msg.value.decode("utf-8"))

                # Only process messages for our test symbol (to avoid cross-talk with running app)
                if msg.topic == settings.KAFKA_TRADES_TOPIC:
                    if payload.get("symbol") == symbol:
                        events_received["trades"] += 1
                        assert payload["quantity"] == "5.0"
                        assert payload["price"] == "100.0"

                elif msg.topic == settings.KAFKA_ORDER_UPDATES_TOPIC:
                    if payload.get("order_id") == sell_order["id"] and payload.get("status") == "FILLED":
                        events_received["updates_sell_filled"] = True
                    if payload.get("order_id") == buy_order["id"] and payload.get("status") == "FILLED":
                        events_received["updates_buy_filled"] = True

                if events_received["trades"] == 1 and events_received["updates_sell_filled"] and events_received["updates_buy_filled"]:
                    return True # Success

        try:
            await asyncio.wait_for(wait_for_messages(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail(f"Timeout waiting for messages. Received: {events_received}")

    finally:
        await producer.stop()
        await consumer.stop()

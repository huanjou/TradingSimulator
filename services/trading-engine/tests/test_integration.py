import asyncio
import json
import uuid

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from app.core.config import settings


@pytest.mark.asyncio
async def test_kafka_integration():
    # 1. Start Producer to send mock order and market data
    producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BROKER)
    await producer.start()

    # 2. Start Consumer to read from trades and order_updates
    # We use a unique group_id so we get all messages
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TRADES_TOPIC,
        settings.KAFKA_ORDER_UPDATES_TOPIC,
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id=f"test-group-{uuid.uuid4()}",
        auto_offset_reset="latest",  # We only care about messages produced during this test  # noqa: E501
    )
    await consumer.start()

    try:
        # Create a unique symbol for isolation
        symbol = f"TEST{uuid.uuid4().hex[:4]}/USDT"

        # We will post market data for this symbol
        market_data = {"symbol": symbol, "bid_price": 50000.0, "ask_price": 50010.0}

        # And then post a MARKET BUY order
        buy_order = {
            "id": str(uuid.uuid4()),
            "user_id": "taker",
            "symbol": symbol,
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "5.0",
        }

        # Provide balance to taker
        deposit_command = {
            "type": "DEPOSIT",
            "user_id": "taker",
            "currency": "USDT",
            "amount": 500000.0,
        }
        await producer.send_and_wait(
            settings.KAFKA_WALLET_COMMANDS_TOPIC,
            json.dumps(deposit_command).encode("utf-8"),
        )

        # Publish market data
        await producer.send_and_wait(
            settings.KAFKA_MARKET_DATA_TOPIC, json.dumps(market_data).encode("utf-8")
        )

        # Publish order initially
        current_order_id = buy_order["id"]
        await producer.send_and_wait(
            settings.KAFKA_ORDERS_TOPIC, json.dumps(buy_order).encode("utf-8")
        )

        # Now listen for the results
        # We expect:
        # 1. TradeEvent
        # 2. OrderUpdate for BUY (FILLED)
        events_received = {
            "trades": 0,
            "updates_buy_filled": False,
        }

        async def wait_for_messages():
            nonlocal current_order_id
            async for msg in consumer:
                payload = json.loads(msg.value.decode("utf-8"))

                # Only process messages for our test symbol
                if msg.topic == settings.KAFKA_TRADES_TOPIC:
                    if payload.get("symbol") == symbol:
                        events_received["trades"] += 1
                        assert payload["quantity"] == "5.0"
                        assert payload["price"] == "50010.0"  # BUY at ASK

                elif msg.topic == settings.KAFKA_ORDER_UPDATES_TOPIC:
                    if payload.get("order_id") == current_order_id:
                        if payload.get("status") == "FILLED":
                            events_received["updates_buy_filled"] = True
                        elif payload.get("status") == "REJECTED":
                            # Market data or balance hasn't been processed yet.
                            # Retry by sending a new order.
                            current_order_id = str(uuid.uuid4())
                            buy_order["id"] = current_order_id
                            await producer.send_and_wait(
                                settings.KAFKA_ORDERS_TOPIC,
                                json.dumps(buy_order).encode("utf-8"),
                            )

                if (
                    events_received["trades"] >= 1
                    and events_received["updates_buy_filled"]
                ):
                    return True  # Success

        try:
            await asyncio.wait_for(wait_for_messages(), timeout=15.0)
        except asyncio.TimeoutError:
            pytest.fail(f"Timeout waiting for messages. Received: {events_received}")

    finally:
        await producer.stop()
        await consumer.stop()

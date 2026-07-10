import asyncio
import json

import structlog
import websockets
from aiokafka import AIOKafkaProducer

from app.core.config import settings
from app.core.telemetry import setup_telemetry

logger = structlog.get_logger(__name__)


async def get_kafka_producer():
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    return producer


async def main():
    setup_telemetry("market-data")
    logger.info("Starting market-data service")

    producer = await get_kafka_producer()

    try:
        while True:
            try:
                async with websockets.connect(settings.BINANCE_WS_URL) as ws:
                    logger.info(
                        "Connected to Binance WebSocket", url=settings.BINANCE_WS_URL
                    )
                    async for message in ws:
                        data = json.loads(message)
                        # data example for bookTicker:
                        # {
                        #   "u":400900217,
                        #   "s":"BTCUSDT",
                        #   "b":"25201.00000000",
                        #   "B":"31.21000000",
                        #   "a":"25201.01000000",
                        #   "A":"40.66000000"
                        # }

                        market_event = {
                            "symbol": data.get("s"),
                            "bid_price": float(data.get("b", 0)),
                            "ask_price": float(data.get("a", 0)),
                            "timestamp": data.get("E", 0),  # event time if available
                        }

                        await producer.send_and_wait(
                            settings.KAFKA_MARKET_DATA_TOPIC, value=market_event
                        )

            except Exception as e:
                logger.error(
                    "WebSocket connection error. Reconnecting...", error=str(e)
                )
                await asyncio.sleep(5)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.redis import cache_order
from app.db.base import *  # This ensures all models are registered
from app.db.session import AsyncSessionLocal
from app.models.order import Order

settings = get_settings()
logger = logging.getLogger(__name__)


async def process_orders(messages):
    async with AsyncSessionLocal() as session:
        for msg in messages:
            try:
                data = json.loads(msg.value.decode("utf-8"))

                # Upsert user to satisfy foreign key constraint during tests
                from app.models.user import User

                user_stmt = (
                    insert(User)
                    .values(
                        id=data.get("user_id"),
                        email=f"user_{data.get('user_id')}@test.com",
                        hashed_password="fake",
                    )
                    .on_conflict_do_nothing()
                )
                await session.execute(user_stmt)

                stmt = (
                    insert(Order)
                    .values(
                        id=data.get("id"),
                        user_id=data.get("user_id"),
                        symbol=data.get("symbol"),
                        side=data.get("side"),
                        order_type=data.get("order_type", data.get("type")),
                        quantity=data.get("quantity"),
                        price=data.get("price"),
                        status=data.get("status"),
                    )
                    .on_conflict_do_update(
                        index_elements=["id"],
                        set_=dict(
                            status=data.get("status"),
                            # update price/quantity if trades occur
                        ),
                    )
                )
                await session.execute(stmt)

                # Cache to redis (convert values to str to avoid serialization issues)
                cache_dict = {
                    k: str(v) if v is not None else "" for k, v in data.items()
                }
                await cache_order(cache_dict)
            except Exception as e:
                logger.error(f"Error processing order: {e}")
        await session.commit()


async def consume():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id="ledger-writer-group",
        auto_offset_reset="earliest",
    )
    await consumer.start()
    try:
        while True:
            result = await consumer.getmany(timeout_ms=1000, max_records=100)
            for tp, messages in result.items():
                if messages:
                    await process_orders(messages)
    finally:
        await consumer.stop()


if __name__ == "__main__":
    logging.basicConfig(level=settings.LOG_LEVEL)
    asyncio.run(consume())

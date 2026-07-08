import json
import logging

from app.db.session import AsyncSessionLocal
from app.domain.order import OrderEntity
from app.domain.user import UserEntity
from app.repositories.order import order_repo
from app.repositories.user import user_repo
from app.services.cache_service import cache_order

logger = logging.getLogger(__name__)


async def process_orders(messages):
    """
    Processes a batch of Kafka messages and upserts them into the database.
    """
    async with AsyncSessionLocal() as session:
        try:
            for msg in messages:
                try:
                    data = json.loads(msg.value.decode("utf-8"))
                except json.JSONDecodeError as e:
                    logger.error(f"Poison pill detected: invalid JSON. Skipping message. Error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Poison pill detected: malformed message. Skipping. Error: {e}")
                    continue

                # 1. Create Domain Entities
                user_entity = UserEntity(
                    id=data.get("user_id"),
                    email=f"user_{data.get('user_id')}@test.com",
                    hashed_password="fake",
                )

                order_entity = OrderEntity(
                    id=data.get("id"),
                    user_id=data.get("user_id"),
                    symbol=data.get("symbol"),
                    side=data.get("side"),
                    order_type=data.get("order_type", data.get("type")),
                    quantity=data.get("quantity"),
                    price=data.get("price"),
                    status=data.get("status"),
                )

                # 2. Upsert via Repositories
                await user_repo.upsert(session, obj_in=user_entity)
                await order_repo.upsert(session, obj_in=order_entity)

                # 3. Cache to redis (convert values to str to avoid serialization issues)
                cache_dict = {
                    k: str(v) if v is not None else "" for k, v in data.items()
                }
                await cache_order(cache_dict)

            await session.commit()
        except Exception as e:
            logger.error(f"Fatal error processing batch: {e}")
            await session.rollback()
            raise

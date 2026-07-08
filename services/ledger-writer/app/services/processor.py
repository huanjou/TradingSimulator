import json
import structlog

from app.db.session import AsyncSessionLocal
from app.domain.order import OrderEntity
from app.domain.user import UserEntity
from app.repositories.order import order_repo
from app.repositories.user import user_repo
from app.services.cache_service import cache_order

from opentelemetry import metrics

logger = structlog.get_logger(__name__)

meter = metrics.get_meter(__name__)
ledger_writes_counter = meter.create_counter(
    "ledger_writes_total",
    description="Total number of database upserts processed by ledger-writer",
)
ledger_write_errors_counter = meter.create_counter(
    "ledger_write_errors_total",
    description="Total number of database errors encountered by ledger-writer",
)

async def process_orders(messages, topic: str = "orders"):
    """
    Processes a batch of Kafka messages and upserts them into the database.
    """
    async with AsyncSessionLocal() as session:
        try:
            for msg in messages:
                try:
                    data = json.loads(msg.value.decode("utf-8"))
                except json.JSONDecodeError as e:
                    ledger_write_errors_counter.add(1, {"reason": "invalid_json"})
                    logger.error("poison_pill_detected", reason="invalid_json", error=str(e))
                    continue
                except Exception as e:
                    ledger_write_errors_counter.add(1, {"reason": "malformed_message"})
                    logger.error("poison_pill_detected", reason="malformed_message", error=str(e))
                    continue

                if topic == "orders":
                    # 1. Create Domain Entities for new order
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
                        status=data.get("status", "PENDING"),
                    )

                    # 2. Upsert via Repositories
                    await user_repo.upsert(session, obj_in=user_entity)
                    await order_repo.upsert(session, obj_in=order_entity)
                    ledger_writes_counter.add(1, {"type": "order_insert"})
                
                elif topic == "order_updates":
                    # Update order status and filled_quantity
                    order_id = data.get("order_id") or data.get("id")
                    status = data.get("status")
                    try:
                        filled_quantity = float(data.get("filled_quantity", 0.0))
                    except (ValueError, TypeError):
                        filled_quantity = 0.0
                    
                    if order_id and status:
                        await order_repo.update_status(
                            session, 
                            order_id=order_id, 
                            status=status, 
                            filled_quantity=filled_quantity
                        )
                        ledger_writes_counter.add(1, {"type": "order_update"})

                # 3. Cache to redis (convert values to str to avoid serialization issues)
                cache_dict = {
                    k: str(v) if v is not None else "" for k, v in data.items()
                }
                await cache_order(cache_dict)

            await session.commit()
        except Exception as e:
            ledger_write_errors_counter.add(1, {"reason": "commit_failed"})
            logger.error("batch_processing_failed", error=str(e), exc_info=True)
            await session.rollback()
            raise

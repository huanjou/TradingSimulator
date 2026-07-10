import orjson
import structlog
from opentelemetry import metrics

from app.db.session import AsyncSessionLocal
from app.repositories.order import order_repo
from app.repositories.user import user_repo

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
            order_inserts = {}
            user_inserts = {}
            order_updates = {}

            for msg in messages:
                try:
                    data = orjson.loads(msg.value)
                except orjson.JSONDecodeError as e:
                    ledger_write_errors_counter.add(1, {"reason": "invalid_json"})
                    logger.error(
                        "poison_pill_detected", reason="invalid_json", error=str(e)
                    )
                    continue
                except Exception as e:
                    ledger_write_errors_counter.add(1, {"reason": "malformed_message"})
                    logger.error(
                        "poison_pill_detected", reason="malformed_message", error=str(e)
                    )
                    continue

                if topic == "orders":
                    user_id = data.get("user_id")
                    if user_id:
                        user_inserts[user_id] = {
                            "id": user_id,
                            "email": f"user_{user_id}@test.com",
                            "hashed_password": "fake",
                        }

                    order_id = data.get("id")
                    if order_id:
                        order_inserts[order_id] = {
                            "id": order_id,
                            "user_id": data.get("user_id"),
                            "symbol": data.get("symbol"),
                            "side": data.get("side"),
                            "order_type": data.get("order_type", data.get("type")),
                            "quantity": float(data.get("quantity") or 0.0),
                            "filled_quantity": 0.0,
                            "price": float(data.get("price") or 0.0),
                            "status": data.get("status", "PENDING"),
                        }

                elif topic == "order_updates":
                    order_id = data.get("order_id") or data.get("id")
                    status = data.get("status")
                    try:
                        filled_quantity = float(data.get("filled_quantity") or 0.0)
                    except (ValueError, TypeError):
                        filled_quantity = 0.0

                    if order_id and status:
                        order_updates[order_id] = {
                            "id": order_id,
                            "status": status,
                            "filled_quantity": filled_quantity,
                        }

            user_inserts_list = list(user_inserts.values())
            order_inserts_list = list(order_inserts.values())
            order_updates_list = list(order_updates.values())

            if user_inserts_list:
                await user_repo.upsert_bulk(session, user_inserts_list)
            if order_inserts_list:
                await order_repo.upsert_bulk(session, order_inserts_list)
                ledger_writes_counter.add(len(order_inserts), {"type": "order_insert"})
            if order_updates_list:
                try:
                    await order_repo.update_status_bulk(session, order_updates_list)
                    ledger_writes_counter.add(
                        len(order_updates_list), {"type": "order_update"}
                    )
                except Exception as e:
                    # SQLAlchemy raises StaleDataError if it expects to update N rows but updates < N rows.
                    # This happens due to eventual consistency (Kafka delivers update before insert).
                    logger.warning(
                        "bulk_update_failed_fallback_to_individual", error=str(e)
                    )
                    await session.rollback()
                    for update_data in order_updates_list:
                        try:
                            await order_repo.update_status(
                                session,
                                update_data["id"],
                                update_data["status"],
                                update_data["filled_quantity"],
                            )
                            await session.commit()
                        except Exception as inner_e:
                            logger.error(
                                "individual_update_failed_stale_data",
                                order_id=update_data["id"],
                                error=str(inner_e),
                            )
                            await session.rollback()

            await session.commit()
        except Exception as e:
            ledger_write_errors_counter.add(1, {"reason": "commit_failed"})
            logger.error("batch_processing_failed", error=str(e), exc_info=True)
            await session.rollback()
            raise

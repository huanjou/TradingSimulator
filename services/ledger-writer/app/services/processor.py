from decimal import Decimal, InvalidOperation

import orjson
import structlog
from app.core.utils import is_valid_uuid
from app.repositories.balance import BalanceRepository
from app.repositories.order import OrderRepository
from app.repositories.symbol import SymbolRepository
from app.repositories.trade import TradeRepository
from opentelemetry import metrics
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


def _to_decimal(value, default: str = "0") -> Decimal:
    """Parse a monetary value into an exact Decimal.

    Values arrive as JSON strings (engine events) or numbers. Converting via
    ``str`` avoids binary float rounding errors when the source is a float.
    """
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


meter = metrics.get_meter(__name__)
ledger_writes_counter = meter.create_counter(
    "ledger_writes_total",
    description="Total number of database upserts processed by ledger-writer",
)
ledger_write_errors_counter = meter.create_counter(
    "ledger_write_errors_total",
    description="Total number of database errors encountered by ledger-writer",
)


async def process_orders(
    messages,
    session: AsyncSession,
    order_repo: OrderRepository,
    trade_repo: TradeRepository,
    symbol_repo: SymbolRepository,
    balance_repo: BalanceRepository = None,
    topic: str = "orders",
):
    """
    Processes a batch of Kafka messages and upserts them into the database.
    """
    try:
        order_inserts = {}

        order_updates = {}
        trade_inserts = {}
        balance_upserts = {}
        system_events = []

        for msg in messages:
            try:
                data = orjson.loads(msg.value)
                if not isinstance(data, dict):
                    raise ValueError("Payload must be a JSON object")
            except orjson.JSONDecodeError as e:
                ledger_write_errors_counter.add(1, {"reason": "invalid_json"})
                logger.error(
                    "poison_pill_detected", reason="invalid_json", error=str(e)
                )
                continue
            except (ValueError, TypeError) as e:
                ledger_write_errors_counter.add(1, {"reason": "malformed_message"})
                logger.error(
                    "poison_pill_detected", reason="malformed_message", error=str(e)
                )
                continue

            if topic == "orders":
                order_id = data.get("id")
                if (
                    order_id
                    and is_valid_uuid(order_id)
                    and is_valid_uuid(data.get("user_id"))
                ):
                    order_inserts[order_id] = {
                        "id": order_id,
                        "user_id": data.get("user_id"),
                        "symbol": data.get("symbol"),
                        "side": data.get("side"),
                        "order_type": data.get("order_type", data.get("type")),
                        "quantity": _to_decimal(data.get("quantity")),
                        "filled_quantity": Decimal("0"),
                        "price": _to_decimal(data.get("price")),
                        "status": data.get("status", "PENDING"),
                    }
                else:
                    logger.warning("ignored_order_invalid_uuids", data=data)

            elif topic == "order_updates":
                order_id = data.get("order_id") or data.get("id")
                status = data.get("status")
                filled_quantity = _to_decimal(data.get("filled_quantity"))

                average_fill_price_raw = data.get("average_fill_price")
                average_fill_price = (
                    _to_decimal(average_fill_price_raw)
                    if average_fill_price_raw is not None
                    else None
                )

                if order_id and status and is_valid_uuid(order_id):
                    order_updates[order_id] = {
                        "id": order_id,
                        "status": status,
                        "filled_quantity": filled_quantity,
                        "average_fill_price": average_fill_price,
                    }
                else:
                    logger.warning("ignored_order_update_invalid_data", data=data)

            elif topic == "trades":
                trade_id = data.get("trade_id") or data.get("id")
                order_id = data.get("order_id")
                if (
                    trade_id
                    and order_id
                    and is_valid_uuid(trade_id)
                    and is_valid_uuid(order_id)
                ):
                    trade_inserts[trade_id] = {
                        "id": trade_id,
                        "order_id": order_id,
                        "symbol": data.get("symbol"),
                        "price": _to_decimal(data.get("price")),
                        "quantity": _to_decimal(data.get("quantity")),
                        "timestamp": float(data.get("timestamp") or 0.0),
                    }
                else:
                    logger.warning("ignored_trade_invalid_data", data=data)

            elif topic == "system_events":
                system_events.append(data)

            elif topic == "balance_updates":
                user_id = data.get("user_id")
                currency = data.get("currency")
                if user_id and currency:
                    key = f"{user_id}_{currency}"
                    balance_upserts[key] = {
                        "user_id": user_id,
                        "currency": currency,
                        "available": _to_decimal(data.get("available")),
                        "locked": _to_decimal(data.get("locked")),
                    }
                else:
                    logger.warning("ignored_balance_invalid_data", data=data)

        order_inserts_list = list(order_inserts.values())
        order_updates_list = list(order_updates.values())
        trade_inserts_list = list(trade_inserts.values())
        balance_upserts_list = list(balance_upserts.values())

        # Order status updates run first, in their own commit scope: the bulk
        # path can fail due to eventual consistency (Kafka delivers the update
        # before the insert) and its per-row fallback commits/rollbacks must
        # not interfere with the atomic write transaction below.
        if order_updates_list:
            try:
                await order_repo.update_status_bulk(session, order_updates_list)
                ledger_writes_counter.add(
                    len(order_updates_list), {"type": "order_update"}
                )
            except Exception as e:
                # SQLAlchemy raises StaleDataError if it expects to update N rows but updates < N rows.  # noqa: E501
                # This happens due to eventual consistency (Kafka delivers update before insert).  # noqa: E501
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
                            update_data["average_fill_price"],
                        )
                        await session.commit()
                    except Exception as inner_e:
                        logger.error(
                            "individual_update_failed_stale_data",
                            order_id=update_data["id"],
                            error=str(inner_e),
                        )
                        await session.rollback()

        # Order inserts, trade inserts, balance upserts and symbol events all
        # share a single transaction with a single commit below, so a crash
        # can never persist a trade without its matching balance update.
        if order_inserts_list:
            await order_repo.upsert_bulk(session, order_inserts_list)
            ledger_writes_counter.add(len(order_inserts), {"type": "order_insert"})

        if trade_inserts_list:
            await trade_repo.upsert_bulk(session, trade_inserts_list)
            ledger_writes_counter.add(len(trade_inserts), {"type": "trade_insert"})

        if balance_upserts_list and balance_repo:
            await balance_repo.upsert_bulk(session, balance_upserts_list)
            ledger_writes_counter.add(
                len(balance_upserts_list), {"type": "balance_upsert"}
            )

        for event in system_events:
            if event.get("type") == "SYMBOL_CREATED":
                symbol_name = event.get("symbol")
                if symbol_name:
                    await symbol_repo.upsert(session, symbol_name)
                    logger.info("symbol_created_in_db", symbol=symbol_name)

        # Single commit for the whole batch: trades and balances land
        # atomically or not at all.
        await session.commit()
    except Exception as e:
        ledger_write_errors_counter.add(1, {"reason": "ledger_write_failed"})
        logger.error("ledger_write_failed", error=str(e), exc_info=True)
        await session.rollback()
        raise  # Let the caller handle retry/offset management

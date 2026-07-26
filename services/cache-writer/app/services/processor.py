import orjson
import structlog
from app.services.cache_service import cache_orders_bulk
from opentelemetry import metrics

logger = structlog.get_logger(__name__)

meter = metrics.get_meter(__name__)
cache_writes_counter = meter.create_counter(
    "cache_writes_total",
    description="Total number of cache updates processed by cache-writer",
)
cache_write_errors_counter = meter.create_counter(
    "cache_write_errors_total",
    description="Total number of cache errors encountered by cache-writer",
)


async def process_orders(messages, topic: str = "orders"):
    """
    Processes a batch of Kafka messages and updates them in Redis cache.
    """
    try:
        cache_dicts = []
        for msg in messages:
            try:
                data = orjson.loads(msg.value)
            except orjson.JSONDecodeError as e:
                cache_write_errors_counter.add(1, {"reason": "invalid_json"})
                logger.error(
                    "poison_pill_detected", reason="invalid_json", error=str(e)
                )
                continue
            except Exception as e:
                cache_write_errors_counter.add(1, {"reason": "malformed_message"})
                logger.error(
                    "poison_pill_detected", reason="malformed_message", error=str(e)
                )
                continue

            # Convert values to str to avoid serialization issues in Redis hashes
            cache_dict = {}
            for k, v in data.items():
                if v is None:
                    cache_dict[k] = ""
                elif isinstance(v, dict | list):
                    cache_dict[k] = orjson.dumps(v).decode("utf-8")
                else:
                    cache_dict[k] = str(v)

            cache_dicts.append(cache_dict)

        if cache_dicts:
            await cache_orders_bulk(cache_dicts)
            cache_writes_counter.add(len(cache_dicts), {"type": "cache_upsert"})

    except Exception as e:
        cache_write_errors_counter.add(1, {"reason": "batch_failed"})
        logger.error("batch_processing_failed", error=str(e), exc_info=True)
        raise


async def process_balances(messages):
    from app.services.cache_service import cache_balances_bulk

    try:
        cache_dicts = []
        for msg in messages:
            try:
                data = orjson.loads(msg.value)
                cache_dicts.append(data)
            except Exception as e:
                logger.error(
                    "poison_pill_detected", reason="invalid_json", error=str(e)
                )
                continue
        if cache_dicts:
            await cache_balances_bulk(cache_dicts)
            cache_writes_counter.add(
                len(cache_dicts), {"type": "cache_upsert_balances"}
            )
    except Exception as e:
        cache_write_errors_counter.add(1, {"reason": "batch_failed"})
        logger.error("batch_processing_failed", error=str(e), exc_info=True)
        raise

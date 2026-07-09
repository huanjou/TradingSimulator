import orjson
import structlog
from opentelemetry import metrics

from app.services.cache_service import cache_orders_bulk

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
            cache_dict = {k: str(v) if v is not None else "" for k, v in data.items()}
            cache_dicts.append(cache_dict)

        if cache_dicts:
            await cache_orders_bulk(cache_dicts)
            cache_writes_counter.add(len(cache_dicts), {"type": "cache_upsert"})

    except Exception as e:
        cache_write_errors_counter.add(1, {"reason": "batch_failed"})
        logger.error("batch_processing_failed", error=str(e), exc_info=True)
        raise

import structlog
import uuid

from aiokafka import AIOKafkaConsumer

from app.core.config import get_settings
from app.services.processor import process_orders

settings = get_settings()
logger = structlog.get_logger(__name__)


async def consume():
    """
    Kafka consumer loop for the ledger-writer service.
    Pulls batches of orders and hands them off to the processor.
    """
    consumer = AIOKafkaConsumer(
        "orders",
        settings.KAFKA_ORDER_UPDATES_TOPIC,
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id="ledger-writer-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    logger.info("consumer_started", topics=["orders", settings.KAFKA_ORDER_UPDATES_TOPIC])
    try:
        while True:
            # Fetch in batches for efficiency
            result = await consumer.getmany(timeout_ms=1000, max_records=100)
            for tp, messages in result.items():
                if messages:
                    structlog.contextvars.clear_contextvars()
                    structlog.contextvars.bind_contextvars(
                        batch_id=str(uuid.uuid4()),
                        topic=tp.topic,
                        partition=tp.partition,
                        messages_count=len(messages),
                    )
                    logger.info("processing_batch")
                    await process_orders(messages, topic=tp.topic)
                    await consumer.commit({tp: messages[-1].offset + 1})

    finally:
        await consumer.stop()

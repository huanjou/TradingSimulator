import logging

from aiokafka import AIOKafkaConsumer

from app.core.config import get_settings
from app.services.processor import process_orders

settings = get_settings()
logger = logging.getLogger(__name__)


async def consume():
    """
    Kafka consumer loop for the ledger-writer service.
    Pulls batches of orders and hands them off to the processor.
    """
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id="ledger-writer-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    logger.info("Started consuming from Kafka topic 'orders'...")
    try:
        while True:
            # Fetch in batches for efficiency
            result = await consumer.getmany(timeout_ms=1000, max_records=100)
            for tp, messages in result.items():
                if messages:
                    await process_orders(messages)
                    await consumer.commit({tp: messages[-1].offset + 1})

    finally:
        await consumer.stop()

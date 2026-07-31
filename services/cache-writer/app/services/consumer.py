import uuid

import structlog
from aiokafka import AIOKafkaConsumer
from app.core.config import get_settings
from app.services.processor import process_balances, process_orders

settings = get_settings()
logger = structlog.get_logger(__name__)


async def consume(shutdown_event=None):
    """
    Kafka consumer loop for the ledger-writer service.
    Pulls batches of orders and hands them off to the processor.
    Exits after the in-flight batch once ``shutdown_event`` is set.
    """
    consumer = AIOKafkaConsumer(
        "orders",
        settings.KAFKA_ORDER_UPDATES_TOPIC,
        settings.KAFKA_BALANCE_UPDATES_TOPIC,
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        isolation_level="read_committed",
        session_timeout_ms=10000,
        heartbeat_interval_ms=3000,
    )

    # Retry loop for starting consumer
    max_retries = 30
    import asyncio

    for attempt in range(max_retries):
        try:
            await consumer.start()
            break
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(
                    "Failed to start Kafka consumer after multiple attempts",
                    error=str(e),
                )
                raise
            logger.warning(
                "Failed to connect to Kafka, retrying...",
                attempt=attempt + 1,
                error=str(e),
            )
            await asyncio.sleep(2)

    logger.info(
        "consumer_started",
        topics=[
            "orders",
            settings.KAFKA_ORDER_UPDATES_TOPIC,
            settings.KAFKA_BALANCE_UPDATES_TOPIC,
        ],
    )
    try:
        while shutdown_event is None or not shutdown_event.is_set():
            # Fetch in batches for efficiency
            result = await consumer.getmany(timeout_ms=1000, max_records=100)
            for tp, messages in result.items():
                if messages:
                    from opentelemetry import propagate, trace

                    tracer = trace.get_tracer(__name__)

                    links = []
                    for msg in messages:
                        if msg.headers:
                            headers_dict = {
                                k: v.decode("utf-8") for k, v in msg.headers
                            }
                            ctx = propagate.extract(headers_dict)
                            span_context = trace.get_current_span(
                                ctx
                            ).get_span_context()
                            if span_context.is_valid:
                                links.append(trace.Link(span_context))

                    structlog.contextvars.clear_contextvars()
                    structlog.contextvars.bind_contextvars(
                        batch_id=str(uuid.uuid4()),
                        topic=tp.topic,
                        partition=tp.partition,
                        messages_count=len(messages),
                    )

                    with tracer.start_as_current_span(
                        f"process_batch {tp.topic}",
                        links=links,
                        kind=trace.SpanKind.CONSUMER,
                    ):
                        logger.info("processing_batch")
                        if tp.topic in (settings.KAFKA_ORDER_UPDATES_TOPIC, "orders"):
                            await process_orders(messages, topic=tp.topic)
                        elif tp.topic == settings.KAFKA_BALANCE_UPDATES_TOPIC:
                            await process_balances(messages)
                        await consumer.commit({tp: messages[-1].offset + 1})

    finally:
        await consumer.stop()

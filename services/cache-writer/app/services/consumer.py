import uuid

import structlog
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
        group_id="cache-writer-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    logger.info(
        "consumer_started", topics=["orders", settings.KAFKA_ORDER_UPDATES_TOPIC]
    )
    try:
        while True:
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
                        await process_orders(messages, topic=tp.topic)
                        await consumer.commit({tp: messages[-1].offset + 1})

    finally:
        await consumer.stop()

import asyncio
import uuid

import structlog
from aiokafka import AIOKafkaConsumer
from opentelemetry import propagate, trace

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.repositories.order import order_repo
from app.repositories.symbol import symbol_repo
from app.repositories.trade import trade_repo
from app.repositories.balance import balance_repo
from app.services.processor import process_orders

tracer = trace.get_tracer(__name__)

settings = get_settings()
logger = structlog.get_logger(__name__)


async def consume():
    """
    Kafka consumer loop for the ledger-writer service.
    Pulls batches of orders and hands them off to the processor.
    """
    consumer = AIOKafkaConsumer(
        "orders",
        "trades",
        "system_events",
        settings.KAFKA_ORDER_UPDATES_TOPIC,
        settings.KAFKA_BALANCE_UPDATES_TOPIC,
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id="ledger-writer-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    logger.info(
        "consumer_started",
        topics=[
            "orders",
            "trades",
            "system_events",
            settings.KAFKA_ORDER_UPDATES_TOPIC,
            settings.KAFKA_BALANCE_UPDATES_TOPIC,
        ],
    )
    try:
        while True:
            # Fetch in batches for efficiency
            result = await consumer.getmany(timeout_ms=1000, max_records=100)
            for tp, messages in result.items():
                if messages:
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

                        max_retries = 5
                        base_delay = 1.0
                        for attempt in range(max_retries):
                            try:
                                async with AsyncSessionLocal() as session:
                                    await process_orders(
                                        messages,
                                        session=session,
                                        order_repo=order_repo,
                                        trade_repo=trade_repo,
                                        symbol_repo=symbol_repo,
                                        balance_repo=balance_repo,
                                        topic=tp.topic,
                                    )
                                await consumer.commit({tp: messages[-1].offset + 1})
                                break  # Success, exit retry loop
                            except Exception as e:
                                if attempt == max_retries - 1:
                                    logger.error(
                                        "max_retries_reached",
                                        error=str(e),
                                        exc_info=True,
                                    )
                                    raise
                                delay = base_delay * (2**attempt)
                                logger.warning(
                                    "batch_processing_failed_retrying",
                                    error=str(e),
                                    attempt=attempt + 1,
                                    delay=delay,
                                )
                                await asyncio.sleep(delay)

    finally:
        await consumer.stop()

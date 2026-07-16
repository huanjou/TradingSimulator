import uuid
from typing import Awaitable, Callable

import orjson
import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .config import settings

logger = structlog.get_logger(__name__)


class KafkaApp:
    def __init__(
        self,
        order_handler: Callable[[list[dict]], Awaitable[None]],
        market_data_handler: Callable[[list[dict]], Awaitable[None]],
    ):
        self.order_handler = order_handler
        self.market_data_handler = market_data_handler

        self.consumer = AIOKafkaConsumer(
            settings.KAFKA_ORDERS_TOPIC,
            settings.KAFKA_MARKET_DATA_TOPIC,
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id="trading-engine-group",
            auto_offset_reset="earliest",
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKER,
            linger_ms=5,
        )

    async def start(self):
        await self.consumer.start()
        await self.producer.start()
        logger.info(
            "kafka_started",
            topics=[settings.KAFKA_ORDERS_TOPIC, settings.KAFKA_MARKET_DATA_TOPIC],
        )

        try:
            while True:
                # getmany returns dict: {TopicPartition: [ConsumerRecord, ...]}
                data = await self.consumer.getmany(timeout_ms=100, max_records=500)
                if not data:
                    continue

                for _, messages in data.items():
                    await self._process_batch(messages)
        finally:
            await self.stop()

    async def stop(self):
        await self.consumer.stop()
        await self.producer.stop()
        logger.info("kafka_stopped")

    async def _process_batch(self, messages: list):
        if not messages:
            return

        from opentelemetry import propagate, trace

        tracer = trace.get_tracer(__name__)

        # Extract links from headers
        links = []
        for msg in messages:
            if msg.headers:
                headers_dict = {k: v.decode("utf-8") for k, v in msg.headers}
                ctx = propagate.extract(headers_dict)
                span_context = trace.get_current_span(ctx).get_span_context()
                if span_context.is_valid:
                    links.append(trace.Link(span_context))

        topic = messages[0].topic
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            batch_id=str(uuid.uuid4()),
            topic=topic,
            batch_size=len(messages),
        )

        with tracer.start_as_current_span(
            f"process_batch {topic}", links=links, kind=trace.SpanKind.CONSUMER
        ):
            try:
                batch_data = [orjson.loads(msg.value) for msg in messages]
                logger.info("processing_batch", size=len(batch_data))

                if topic == settings.KAFKA_ORDERS_TOPIC:
                    await self.order_handler(batch_data)
                elif topic == settings.KAFKA_MARKET_DATA_TOPIC:
                    await self.market_data_handler(batch_data)
                else:
                    logger.warning("unknown_topic_in_batch", topic=topic)
            except Exception as e:
                logger.error("batch_processing_failed", error=str(e), exc_info=True)

    async def publish(self, topic: str, data: bytes, key: bytes | None = None):
        """Helper method to expose producer publish functionality. Returns a Future."""
        from opentelemetry import propagate

        headers_dict = {}
        propagate.inject(headers_dict)
        kafka_headers = [(k, v.encode("utf-8")) for k, v in headers_dict.items()]

        return await self.producer.send(topic, data, key=key, headers=kafka_headers)

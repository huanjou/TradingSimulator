import uuid
from typing import Awaitable, Callable

import orjson
import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, ConsumerRebalanceListener
from opentelemetry import propagate, trace

from .config import settings

logger = structlog.get_logger(__name__)


class KafkaPublisher:
    def __init__(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKER,
            linger_ms=5,
            acks="all",
        )

    async def start(self):
        max_retries = 30
        import asyncio

        for attempt in range(max_retries):
            try:
                await self.producer.start()
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        "Failed to start Kafka publisher after multiple attempts",
                        error=str(e),
                    )
                    raise
                logger.warning(
                    "Failed to connect to Kafka, retrying...",
                    attempt=attempt + 1,
                    error=str(e),
                )
                await asyncio.sleep(2)

    async def stop(self):
        await self.producer.stop()

    async def publish(self, topic: str, data: bytes, key: bytes | None = None):
        headers_dict = {}
        propagate.inject(headers_dict)
        kafka_headers = [(k, v.encode("utf-8")) for k, v in headers_dict.items()]

        return await self.producer.send(topic, data, key=key, headers=kafka_headers)


class SeekListener(ConsumerRebalanceListener):
    def __init__(self, consumer, initial_offsets, seek_to_end: bool = False):
        self.consumer = consumer
        self.initial_offsets = initial_offsets or {}
        # When rehydrating from Postgres (no snapshot), the durable ledger
        # already reflects all previously applied history, so we resume from the
        # HEAD of the log instead of replaying it against the fresh state.
        self.seek_to_end = seek_to_end

    async def on_partitions_revoked(self, revoked):
        pass

    async def on_partitions_assigned(self, assigned):
        if self.seek_to_end:
            await self.consumer.seek_to_end(*assigned)
            logger.warning(
                "cold_start_seek_to_end",
                partitions=[f"{tp.topic}:{tp.partition}" for tp in assigned],
            )
            return
        for tp in assigned:
            topic = tp.topic
            partition = str(tp.partition)
            if (
                topic in self.initial_offsets
                and partition in self.initial_offsets[topic]
            ):
                seek_offset = self.initial_offsets[topic][partition] + 1
                self.consumer.seek(tp, seek_offset)
                logger.info(
                    "seek_to_snapshot_offset",
                    topic=topic,
                    partition=partition,
                    offset=seek_offset,
                )


class KafkaConsumerRunner:
    def __init__(
        self,
        order_handler: Callable[[list[dict]], Awaitable[None]],
        market_data_handler: Callable[[list[dict]], Awaitable[None]],
        wallet_commands_handler: Callable[[list[dict]], Awaitable[None]],
        initial_offsets: dict = None,
        seek_to_end: bool = False,
    ):
        self.order_handler = order_handler
        self.market_data_handler = market_data_handler
        self.wallet_commands_handler = wallet_commands_handler
        self.initial_offsets = initial_offsets or {}
        self.seek_to_end = seek_to_end
        # Deep copy to maintain state
        self.current_offsets = {
            t: {p: o for p, o in parts.items()}
            for t, parts in self.initial_offsets.items()
        }

        self.consumer = AIOKafkaConsumer(
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id="trading-engine-group",
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # Explicitly disable to avoid data loss
            isolation_level="read_committed",
            session_timeout_ms=10000,
            heartbeat_interval_ms=3000,
        )
        self.consumer.subscribe(
            [
                settings.KAFKA_ORDERS_TOPIC,
                settings.KAFKA_MARKET_DATA_TOPIC,
                settings.KAFKA_WALLET_COMMANDS_TOPIC,
            ],
            listener=SeekListener(
                self.consumer, self.initial_offsets, seek_to_end=self.seek_to_end
            ),
        )

    async def start(self):
        max_retries = 30
        import asyncio

        for attempt in range(max_retries):
            try:
                await self.consumer.start()
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
            "kafka_consumer_started",
            topics=[
                settings.KAFKA_ORDERS_TOPIC,
                settings.KAFKA_MARKET_DATA_TOPIC,
                settings.KAFKA_WALLET_COMMANDS_TOPIC,
            ],
        )

        try:
            while True:
                # Reduce timeout from 100ms to 1ms for ultra-low latency,
                # but keep batching if high throughput arrives instantly.
                data = await self.consumer.getmany(timeout_ms=1, max_records=500)
                if not data:
                    continue

                for topic_partition, messages in data.items():
                    await self._process_batch(topic_partition, messages)
        finally:
            await self.stop()

    async def stop(self):
        await self.consumer.stop()
        logger.info("kafka_consumer_stopped")

    async def _process_batch(self, topic_partition, messages: list):
        if not messages:
            return

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

        topic = topic_partition.topic
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
                # Safe parsing to avoid poisoning the whole batch
                batch_data = []
                for msg in messages:
                    try:
                        batch_data.append(orjson.loads(msg.value))
                    except Exception as e:
                        logger.error(
                            "message_parsing_failed", error=str(e), offset=msg.offset
                        )
                        continue

                if not batch_data:
                    # All messages were invalid, commit and move on
                    await self.consumer.commit(
                        {topic_partition: messages[-1].offset + 1}
                    )
                    return

                logger.info("processing_batch", size=len(batch_data))

                if topic == settings.KAFKA_ORDERS_TOPIC:
                    await self.order_handler(batch_data)
                elif topic == settings.KAFKA_MARKET_DATA_TOPIC:
                    await self.market_data_handler(batch_data)
                elif topic == settings.KAFKA_WALLET_COMMANDS_TOPIC:
                    await self.wallet_commands_handler(batch_data)
                else:
                    logger.warning("unknown_topic_in_batch", topic=topic)

                # Manually commit offset after business logic succeeds
                await self.consumer.commit({topic_partition: messages[-1].offset + 1})

                # Update current_offsets for snapshotting
                topic_name = topic_partition.topic
                part_id = str(topic_partition.partition)
                if topic_name not in self.current_offsets:
                    self.current_offsets[topic_name] = {}
                self.current_offsets[topic_name][part_id] = messages[-1].offset

            except Exception as e:
                logger.error("batch_processing_failed", error=str(e), exc_info=True)
                # Re-raise so the consumer crashes instead of losing the batch
                raise

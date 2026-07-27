import asyncio
import json

import structlog
from aiokafka import AIOKafkaConsumer
from app.core.config import get_settings
from app.services.websocket_manager import manager
from opentelemetry import propagate, trace

logger = structlog.get_logger()
settings = get_settings()
tracer = trace.get_tracer(__name__)


class NotificationKafkaConsumer:
    def __init__(self):
        self.consumer = AIOKafkaConsumer(
            settings.KAFKA_ORDER_UPDATES_TOPIC,
            settings.KAFKA_TRADES_TOPIC,
            settings.KAFKA_BALANCE_UPDATES_TOPIC,
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id="notification-ws-group",
            auto_offset_reset="latest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        self.task = None

    async def start(self):
        await self.consumer.start()
        self.task = asyncio.create_task(self._consume())
        logger.info("kafka_consumer_started")

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await self.consumer.stop()
        logger.info("kafka_consumer_stopped")

    async def _consume(self):
        try:
            async for msg in self.consumer:
                topic = msg.topic
                data = msg.value

                # Extract trace context from Kafka headers
                headers_dict = {k: v.decode("utf-8") for k, v in (msg.headers or [])}
                ctx = propagate.extract(headers_dict)

                with tracer.start_as_current_span(
                    f"process_notification {topic}",
                    context=ctx,
                    kind=trace.SpanKind.CONSUMER,
                ):
                    if topic == settings.KAFKA_ORDER_UPDATES_TOPIC:
                        user_id = data.get("user_id")
                        if user_id:
                            payload = json.dumps(
                                {"event": "order_update", "data": data}
                            )
                            await manager.send_personal_message(payload, user_id)
                            logger.info(
                                "order_update_dispatched",
                                user_id=user_id,
                                order_id=data.get("order_id"),
                            )
                        else:
                            logger.warning("order_update_missing_user_id", data=data)

                    elif topic == settings.KAFKA_TRADES_TOPIC:
                        user_id = data.get("user_id")
                        if user_id:
                            payload = json.dumps({"event": "trade", "data": data})
                            await manager.send_personal_message(payload, user_id)
                            logger.info(
                                "trade_dispatched",
                                user_id=user_id,
                                trade_id=data.get("id"),
                            )
                        else:
                            logger.warning("trade_missing_user_id", data=data)

                    elif topic == settings.KAFKA_BALANCE_UPDATES_TOPIC:
                        user_id = data.get("user_id")
                        if user_id:
                            payload = json.dumps(
                                {"event": "balance_update", "data": data}
                            )
                            await manager.send_personal_message(payload, user_id)
                            logger.info(
                                "balance_update_dispatched",
                                user_id=user_id,
                                currency=data.get("currency"),
                            )
                        else:
                            logger.warning("balance_update_missing_user_id", data=data)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("kafka_consume_error", error=str(e))
            # Relaunch the consumer after a short delay
            await asyncio.sleep(5)
            self.task = asyncio.create_task(self._consume())


notification_consumer = NotificationKafkaConsumer()

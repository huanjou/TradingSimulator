import asyncio
from decimal import Decimal
from typing import Protocol

import orjson
import structlog
from app.domain.engine import MatchingEngine
from app.domain.order import Order
from opentelemetry import metrics

logger = structlog.get_logger(__name__)

meter = metrics.get_meter(__name__)
orders_processed_counter = meter.create_counter(
    "orders_processed_total",
    description="Total number of orders processed by the matching engine",
)
trades_executed_counter = meter.create_counter(
    "trades_executed_total",
    description="Total number of trades executed by the matching engine",
)


class MessagePublisher(Protocol):
    async def publish(self, topic: str, message: bytes, key: bytes | None = None):
        pass


class MatchingService:
    def __init__(
        self,
        engine: MatchingEngine,
        publisher: MessagePublisher,
        trades_topic: str,
        updates_topic: str,
    ):
        self.engine = engine
        self.publisher = publisher
        self.trades_topic = trades_topic
        self.updates_topic = updates_topic

    async def handle_orders_batch(self, orders_data: list[dict]) -> None:
        try:
            publish_futures = []

            for order_data in orders_data:
                # 1. Convert to domain model
                order = Order.model_validate(order_data)

                # 2. Execute business logic
                trades, updates = self.engine.process_order(order)

                orders_processed_counter.add(1, {"symbol": order.symbol})
                trades_executed_counter.add(len(trades), {"symbol": order.symbol})

                # 3. Publish results (gather futures)
                for trade in trades:
                    trade_bytes = orjson.dumps(trade.model_dump(mode="json"))
                    publish_futures.append(
                        self.publisher.publish(
                            self.trades_topic,
                            trade_bytes,
                            key=order.symbol.encode("utf-8"),
                        )
                    )
                    logger.info(
                        "trade_published",
                        trade_id=str(trade.id),
                        order_id=str(trade.order_id),
                    )

                for update in updates:
                    update_bytes = orjson.dumps(update.model_dump(mode="json"))
                    publish_futures.append(
                        self.publisher.publish(
                            self.updates_topic,
                            update_bytes,
                            key=order.symbol.encode("utf-8"),
                        )
                    )
                    logger.info(
                        "order_update_published",
                        order_id=str(update.order_id),
                        status=update.status.value,
                    )

            # Await all publishes concurrently
            if publish_futures:
                await asyncio.gather(*publish_futures)

        except Exception as e:
            logger.error("order_batch_handling_failed", error=str(e), exc_info=True)
            raise

    async def handle_market_data_batch(self, market_data_batch: list[dict]) -> None:
        try:
            publish_futures = []

            for md in market_data_batch:
                symbol = md.get("symbol")
                bid = Decimal(str(md.get("bid_price", 0)))
                ask = Decimal(str(md.get("ask_price", 0)))

                trades, updates = self.engine.process_market_data(symbol, bid, ask)

                trades_executed_counter.add(len(trades), {"symbol": symbol})

                # Publish results (gather futures)
                for trade in trades:
                    trade_bytes = orjson.dumps(trade.model_dump(mode="json"))
                    publish_futures.append(
                        self.publisher.publish(
                            self.trades_topic,
                            trade_bytes,
                            key=symbol.encode("utf-8"),
                        )
                    )
                    logger.info(
                        "trade_published_from_md",
                        trade_id=str(trade.id),
                        order_id=str(trade.order_id),
                    )

                for update in updates:
                    update_bytes = orjson.dumps(update.model_dump(mode="json"))
                    publish_futures.append(
                        self.publisher.publish(
                            self.updates_topic,
                            update_bytes,
                            key=symbol.encode("utf-8"),
                        )
                    )
                    logger.info(
                        "order_update_published_from_md",
                        order_id=str(update.order_id),
                        status=update.status.value,
                    )

            # Await all publishes concurrently
            if publish_futures:
                await asyncio.gather(*publish_futures)

        except Exception as e:
            logger.error(
                "market_data_batch_handling_failed", error=str(e), exc_info=True
            )
            raise

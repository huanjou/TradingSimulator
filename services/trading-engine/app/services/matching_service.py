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
    # An order whose depends_on_balance_version has not arrived is deferred at
    # most this many times; after that it is processed normally (the deposit
    # likely came through by then, or funds are truly insufficient).
    MAX_DEFER_ATTEMPTS = 3

    def __init__(
        self,
        engine: MatchingEngine,
        publisher: MessagePublisher,
        trades_topic: str,
        updates_topic: str,
        balance_updates_topic: str,
    ):
        self.engine = engine
        self.publisher = publisher
        self.trades_topic = trades_topic
        self.updates_topic = updates_topic
        self.balance_updates_topic = balance_updates_topic
        # Orders deferred because the balance version they causally depend on
        # (a deposit in the wallet_commands topic) has not been processed yet.
        self._deferred_orders: list[dict] = []

    def _balance_version_reached(self, order_data: dict) -> bool:
        """True when the balance version the order depends on has been applied.

        Backward compatible: orders without depends_on_balance_version pass.
        """
        depends_on = order_data.get("depends_on_balance_version")
        if depends_on is None:
            return True
        current_ver = self.engine.user_balance_versions.get(order_data["user_id"], 0)
        return current_ver >= int(depends_on)

    def _defer_order(self, order_data: dict) -> bool:
        """Defers an order whose funding deposit has not been applied yet.

        Returns True when the order was buffered for a later retry, False when
        it should be processed now (dependency met or retries exhausted).
        """
        if self._balance_version_reached(order_data):
            return False

        attempts = order_data.get("_defer_count", 0)
        if attempts >= self.MAX_DEFER_ATTEMPTS:
            logger.warning(
                "order_defer_attempts_exhausted",
                order_id=order_data.get("id"),
                user_id=order_data.get("user_id"),
                depends_on_balance_version=order_data.get("depends_on_balance_version"),
            )
            return False

        order_data["_defer_count"] = attempts + 1
        self._deferred_orders.append(order_data)
        logger.info(
            "order_deferred_awaiting_balance_version",
            order_id=order_data.get("id"),
            user_id=order_data.get("user_id"),
            depends_on_balance_version=order_data.get("depends_on_balance_version"),
            attempt=attempts + 1,
        )
        return True

    def _process_order_data(self, order_data: dict, publish_futures: list) -> None:
        # 1. Convert to domain model
        order = Order.model_validate(order_data)

        # 2. Execute business logic
        trades, updates, wallet_updates = self.engine.process_order(order)

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

        for w_update in wallet_updates:
            w_update_bytes = orjson.dumps(w_update.model_dump(mode="json"))
            publish_futures.append(
                self.publisher.publish(
                    self.balance_updates_topic,
                    w_update_bytes,
                    key=w_update.user_id.encode("utf-8"),
                )
            )
            logger.info(
                "balance_update_published",
                user_id=w_update.user_id,
                currency=w_update.currency,
            )

    async def handle_orders_batch(self, orders_data: list[dict]) -> None:
        try:
            publish_futures = []

            # Re-check previously deferred orders first: the deposit they
            # depend on may have been processed since the last batch.
            pending = self._deferred_orders + list(orders_data)
            self._deferred_orders = []

            for order_data in pending:
                if self._defer_order(order_data):
                    continue
                self._process_order_data(order_data, publish_futures)

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

                trades, updates, wallet_updates = self.engine.process_market_data(
                    symbol, bid, ask
                )

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

                for w_update in wallet_updates:
                    w_update_bytes = orjson.dumps(w_update.model_dump(mode="json"))
                    publish_futures.append(
                        self.publisher.publish(
                            self.balance_updates_topic,
                            w_update_bytes,
                            key=w_update.user_id.encode("utf-8"),
                        )
                    )
                    logger.info(
                        "balance_update_published_from_md",
                        user_id=w_update.user_id,
                        currency=w_update.currency,
                    )

            # Await all publishes concurrently
            if publish_futures:
                await asyncio.gather(*publish_futures)

        except Exception as e:
            logger.error(
                "market_data_batch_handling_failed", error=str(e), exc_info=True
            )
            raise

    async def handle_wallet_commands_batch(self, commands_data: list[dict]) -> None:
        try:
            publish_futures = []
            for cmd in commands_data:
                if cmd.get("type") == "DEPOSIT":
                    user_id = cmd["user_id"]
                    currency = cmd["currency"]
                    amount = Decimal(str(cmd["amount"]))
                    update = self.engine.process_deposit(user_id, currency, amount)

                    # Record the causal balance version (monotonic per user;
                    # absent on commands from older wallet-service versions).
                    balance_version = cmd.get("balance_version")
                    if balance_version is not None:
                        current_ver = self.engine.user_balance_versions.get(user_id, 0)
                        if int(balance_version) > current_ver:
                            self.engine.user_balance_versions[user_id] = int(
                                balance_version
                            )

                    update_bytes = orjson.dumps(update.model_dump(mode="json"))
                    publish_futures.append(
                        self.publisher.publish(
                            self.balance_updates_topic,
                            update_bytes,
                            key=user_id.encode("utf-8"),
                        )
                    )
                    logger.info(
                        "deposit_processed",
                        user_id=user_id,
                        currency=currency,
                        amount=str(amount),
                    )

            # Deposits may have unblocked deferred orders; process the ones
            # whose causal dependency is now satisfied.
            if self._deferred_orders:
                still_deferred = []
                for order_data in self._deferred_orders:
                    if self._balance_version_reached(order_data):
                        self._process_order_data(order_data, publish_futures)
                    else:
                        still_deferred.append(order_data)
                self._deferred_orders = still_deferred

            if publish_futures:
                await asyncio.gather(*publish_futures)
        except Exception as e:
            logger.error("wallet_commands_handling_failed", error=str(e), exc_info=True)
            raise

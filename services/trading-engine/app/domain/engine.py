import heapq
import itertools
from decimal import Decimal
from typing import Dict, List, Tuple

from .events import BalanceUpdateEvent, OrderUpdateEvent, TradeEvent
from .order import Order, OrderSide, OrderStatus, OrderType


class WalletInfo:
    def __init__(
        self, available: Decimal = Decimal("0"), locked: Decimal = Decimal("0")
    ):
        self.available = available
        self.locked = locked


class MarketPrice:
    def __init__(self, bid: Decimal, ask: Decimal):
        self.bid = bid
        self.ask = ask


class MatchingEngine:
    def __init__(self):
        # symbol -> MarketPrice
        self.market_prices: Dict[str, MarketPrice] = {}
        # Heaps for orders:
        # bids (max-heap): stores (-price, counter, Order)
        self.bids: Dict[str, List[Tuple[Decimal, int, Order]]] = {}
        # asks (min-heap): stores (price, counter, Order)
        self.asks: Dict[str, List[Tuple[Decimal, int, Order]]] = {}
        # user_id -> currency -> WalletInfo
        self.wallets: Dict[str, Dict[str, WalletInfo]] = {}
        self._counter = itertools.count()

    def process_deposit(
        self, user_id: str, currency: str, amount: Decimal
    ) -> BalanceUpdateEvent:
        wallet = self._get_wallet(user_id, currency)
        wallet.available += amount
        return BalanceUpdateEvent(
            user_id=user_id,
            currency=currency,
            available=wallet.available,
            locked=wallet.locked,
        )

    def _get_wallet(self, user_id: str, currency: str) -> WalletInfo:
        if user_id not in self.wallets:
            self.wallets[user_id] = {}
        if currency not in self.wallets[user_id]:
            self.wallets[user_id][currency] = WalletInfo()
        return self.wallets[user_id][currency]

    def get_all_pending_orders(self) -> List[Order]:
        """Returns a flat list of all pending orders for snapshotting."""
        orders = []
        for heap in self.bids.values():
            orders.extend(item[2] for item in heap)
        for heap in self.asks.values():
            orders.extend(item[2] for item in heap)
        return orders

    def restore_orders(self, orders: List[Order]) -> None:
        """Hydrates the engine state with existing pending orders."""
        for order in orders:
            self._add_to_book(order)

    def restore_wallets(self, wallets_data: Dict[str, Dict[str, dict]]) -> None:
        """Hydrates the engine state with wallet balances."""
        for user_id, user_wallets in wallets_data.items():
            for currency, wallet_info in user_wallets.items():
                wallet = self._get_wallet(user_id, currency)
                wallet.available = Decimal(str(wallet_info.get("available", "0")))
                wallet.locked = Decimal(str(wallet_info.get("locked", "0")))

    def _add_to_book(self, order: Order):
        """Helper to add an order to the correct priority queue."""
        if order.symbol not in self.bids:
            self.bids[order.symbol] = []
            self.asks[order.symbol] = []

        if order.side == OrderSide.BUY:
            # Max-heap for bids (using negative price)
            heapq.heappush(
                self.bids[order.symbol], (-order.price, next(self._counter), order)
            )
        else:
            # Min-heap for asks
            heapq.heappush(
                self.asks[order.symbol], (order.price, next(self._counter), order)
            )

    def _execute_trade(
        self, order: Order, price: Decimal
    ) -> Tuple[TradeEvent, OrderUpdateEvent, List[BalanceUpdateEvent]]:
        # Fully fill the order
        order.filled_quantity = order.quantity
        order.status = OrderStatus.FILLED
        order.average_fill_price = price

        base, quote = order.symbol.split("/")
        wallet_updates = []
        base_wallet = self._get_wallet(order.user_id, base)
        quote_wallet = self._get_wallet(order.user_id, quote)

        if order.side == OrderSide.BUY:
            if order.order_type == OrderType.LIMIT:
                locked_quote = order.price * order.quantity
                quote_wallet.locked -= locked_quote
                cost = price * order.quantity
                quote_wallet.available += locked_quote - cost
            else:
                cost = price * order.quantity
                quote_wallet.available -= cost
            base_wallet.available += order.quantity
        else:
            if order.order_type == OrderType.LIMIT:
                locked_base = order.quantity
                base_wallet.locked -= locked_base
            else:
                base_wallet.available -= order.quantity
            revenue = price * order.quantity
            quote_wallet.available += revenue

        wallet_updates.append(
            BalanceUpdateEvent(
                user_id=order.user_id,
                currency=base,
                available=base_wallet.available,
                locked=base_wallet.locked,
            )
        )
        wallet_updates.append(
            BalanceUpdateEvent(
                user_id=order.user_id,
                currency=quote,
                available=quote_wallet.available,
                locked=quote_wallet.locked,
            )
        )

        trade = TradeEvent(
            order_id=order.id,
            user_id=order.user_id,
            symbol=order.symbol,
            price=price,
            quantity=order.quantity,
        )

        update = OrderUpdateEvent(
            order_id=order.id,
            user_id=order.user_id,
            status=order.status,
            filled_quantity=order.filled_quantity,
            average_fill_price=order.average_fill_price,
        )

        return trade, update, wallet_updates

    def process_order(
        self, order: Order
    ) -> Tuple[List[TradeEvent], List[OrderUpdateEvent], List[BalanceUpdateEvent]]:
        trades = []
        updates = []
        wallet_updates = []

        if order.symbol not in self.bids:
            self.bids[order.symbol] = []
            self.asks[order.symbol] = []

        base, quote = order.symbol.split("/")
        base_wallet = self._get_wallet(order.user_id, base)
        quote_wallet = self._get_wallet(order.user_id, quote)

        market_price = self.market_prices.get(order.symbol)

        # Balance checks
        if order.side == OrderSide.BUY:
            if order.order_type == OrderType.LIMIT:
                req_quote = order.price * order.quantity
                if quote_wallet.available < req_quote:
                    order.status = OrderStatus.REJECTED
            else:
                if market_price:
                    req_quote = market_price.ask * order.quantity
                    if quote_wallet.available < req_quote:
                        order.status = OrderStatus.REJECTED
        else:
            req_base = order.quantity
            if base_wallet.available < req_base:
                order.status = OrderStatus.REJECTED

        if order.status == OrderStatus.REJECTED:
            updates.append(
                OrderUpdateEvent(
                    order_id=order.id,
                    user_id=order.user_id,
                    status=order.status,
                    filled_quantity=Decimal("0"),
                )
            )
            return trades, updates, wallet_updates

        if order.order_type == OrderType.MARKET:
            if not market_price:
                # Reject market order if no price available
                order.status = OrderStatus.CANCELED
                updates.append(
                    OrderUpdateEvent(
                        order_id=order.id,
                        user_id=order.user_id,
                        status=order.status,
                        filled_quantity=order.filled_quantity,
                    )
                )
            else:
                # Execute at market price (Ask for BUY, Bid for SELL)
                exec_price = (
                    market_price.ask
                    if order.side == OrderSide.BUY
                    else market_price.bid
                )
                trade, update, w_updates = self._execute_trade(order, exec_price)
                trades.append(trade)
                updates.append(update)
                wallet_updates.extend(w_updates)

        elif order.order_type == OrderType.LIMIT:
            # Check if it crosses current market price
            crossed = False
            if market_price:
                if order.side == OrderSide.BUY and order.price >= market_price.ask:
                    crossed = True
                    exec_price = market_price.ask
                elif order.side == OrderSide.SELL and order.price <= market_price.bid:
                    crossed = True
                    exec_price = market_price.bid

            if crossed:
                trade, update, w_updates = self._execute_trade(order, exec_price)
                trades.append(trade)
                updates.append(update)
                wallet_updates.extend(w_updates)
            else:
                # Lock funds
                if order.side == OrderSide.BUY:
                    req_quote = order.price * order.quantity
                    quote_wallet.available -= req_quote
                    quote_wallet.locked += req_quote
                    wallet_updates.append(
                        BalanceUpdateEvent(
                            user_id=order.user_id,
                            currency=quote,
                            available=quote_wallet.available,
                            locked=quote_wallet.locked,
                        )
                    )
                else:
                    req_base = order.quantity
                    base_wallet.available -= req_base
                    base_wallet.locked += req_base
                    wallet_updates.append(
                        BalanceUpdateEvent(
                            user_id=order.user_id,
                            currency=base,
                            available=base_wallet.available,
                            locked=base_wallet.locked,
                        )
                    )

                # Store in priority queue
                self._add_to_book(order)
                updates.append(
                    OrderUpdateEvent(
                        order_id=order.id,
                        user_id=order.user_id,
                        status=order.status,
                        filled_quantity=order.filled_quantity,
                    )
                )

        return trades, updates, wallet_updates

    def process_market_data(
        self, symbol: str, bid: Decimal, ask: Decimal
    ) -> Tuple[List[TradeEvent], List[OrderUpdateEvent], List[BalanceUpdateEvent]]:
        trades = []
        updates = []
        wallet_updates = []

        # Update current price
        self.market_prices[symbol] = MarketPrice(bid=bid, ask=ask)

        if symbol not in self.bids:
            return trades, updates, wallet_updates

        bids_heap = self.bids[symbol]
        asks_heap = self.asks[symbol]

        # Match pending BUY orders against the new ASK price
        # We want to match buyers who are willing to pay >= current ask
        while bids_heap:
            neg_price, _, order = bids_heap[0]
            if -neg_price >= ask:
                # Crossed! Pop from heap and execute
                heapq.heappop(bids_heap)
                trade, update, w_updates = self._execute_trade(order, ask)
                trades.append(trade)
                updates.append(update)
                wallet_updates.extend(w_updates)
            else:
                # Top of heap doesn't match -> the rest won't match either
                break

        # Match pending SELL orders against the new BID price
        # We want to match sellers who are willing to sell <= current bid
        while asks_heap:
            price, _, order = asks_heap[0]
            if price <= bid:
                # Crossed! Pop from heap and execute
                heapq.heappop(asks_heap)
                trade, update, w_updates = self._execute_trade(order, bid)
                trades.append(trade)
                updates.append(update)
                wallet_updates.extend(w_updates)
            else:
                # Top of heap doesn't match -> the rest won't match either
                break

        return trades, updates, wallet_updates

import heapq
import itertools
from decimal import Decimal
from typing import Dict, List, Tuple

from .events import OrderUpdateEvent, TradeEvent
from .order import Order, OrderSide, OrderStatus, OrderType


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
        self._counter = itertools.count()

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
    ) -> Tuple[TradeEvent, OrderUpdateEvent]:
        # Fully fill the order
        order.filled_quantity = order.quantity
        order.status = OrderStatus.FILLED
        order.average_fill_price = price

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

        return trade, update

    def process_order(
        self, order: Order
    ) -> Tuple[List[TradeEvent], List[OrderUpdateEvent]]:
        trades = []
        updates = []

        if order.symbol not in self.bids:
            self.bids[order.symbol] = []
            self.asks[order.symbol] = []

        market_price = self.market_prices.get(order.symbol)

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
                trade, update = self._execute_trade(order, exec_price)
                trades.append(trade)
                updates.append(update)

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
                trade, update = self._execute_trade(order, exec_price)
                trades.append(trade)
                updates.append(update)
            else:
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

        return trades, updates

    def process_market_data(
        self, symbol: str, bid: Decimal, ask: Decimal
    ) -> Tuple[List[TradeEvent], List[OrderUpdateEvent]]:
        trades = []
        updates = []

        # Update current price
        self.market_prices[symbol] = MarketPrice(bid=bid, ask=ask)

        if symbol not in self.bids:
            return trades, updates

        bids_heap = self.bids[symbol]
        asks_heap = self.asks[symbol]

        # Match pending BUY orders against the new ASK price
        # We want to match buyers who are willing to pay >= current ask
        while bids_heap:
            neg_price, _, order = bids_heap[0]
            if -neg_price >= ask:
                # Crossed! Pop from heap and execute
                heapq.heappop(bids_heap)
                trade, update = self._execute_trade(order, ask)
                trades.append(trade)
                updates.append(update)
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
                trade, update = self._execute_trade(order, bid)
                trades.append(trade)
                updates.append(update)
            else:
                # Top of heap doesn't match -> the rest won't match either
                break

        return trades, updates

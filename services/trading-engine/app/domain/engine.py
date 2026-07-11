from typing import Dict, List, Tuple
from decimal import Decimal

from .order import Order, OrderSide, OrderType, OrderStatus
from .events import TradeEvent, OrderUpdateEvent


class MarketPrice:
    def __init__(self, bid: Decimal, ask: Decimal):
        self.bid = bid
        self.ask = ask


class MatchingEngine:
    def __init__(self):
        # symbol -> MarketPrice
        self.market_prices: Dict[str, MarketPrice] = {}
        # symbol -> list of pending Orders
        self.pending_orders: Dict[str, List[Order]] = {}

    def _execute_trade(
        self, order: Order, price: Decimal
    ) -> Tuple[TradeEvent, OrderUpdateEvent]:
        # Fully fill the order
        trade_qty = order.quantity - order.filled_quantity
        order.filled_quantity = order.quantity
        order.status = OrderStatus.FILLED

        trade = TradeEvent(
            order_id=order.id,
            symbol=order.symbol,
            price=price,
            quantity=trade_qty,
        )

        update = OrderUpdateEvent(
            order_id=order.id,
            status=order.status,
            filled_quantity=order.filled_quantity,
        )

        return trade, update

    def process_order(
        self, order: Order
    ) -> Tuple[List[TradeEvent], List[OrderUpdateEvent]]:
        trades = []
        updates = []

        if order.symbol not in self.pending_orders:
            self.pending_orders[order.symbol] = []

        market_price = self.market_prices.get(order.symbol)

        if order.order_type == OrderType.MARKET:
            if not market_price:
                # Reject market order if no price available
                order.status = OrderStatus.CANCELED
                updates.append(
                    OrderUpdateEvent(
                        order_id=order.id,
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
                # Store as pending
                self.pending_orders[order.symbol].append(order)
                updates.append(
                    OrderUpdateEvent(
                        order_id=order.id,
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

        if symbol not in self.pending_orders:
            return trades, updates

        remaining_orders = []
        for order in self.pending_orders[symbol]:
            crossed = False
            exec_price = Decimal("0")

            if order.side == OrderSide.BUY and order.price >= ask:
                crossed = True
                exec_price = ask
            elif order.side == OrderSide.SELL and order.price <= bid:
                crossed = True
                exec_price = bid

            if crossed:
                trade, update = self._execute_trade(order, exec_price)
                trades.append(trade)
                updates.append(update)
            else:
                remaining_orders.append(order)

        self.pending_orders[symbol] = remaining_orders

        return trades, updates

import bisect
from typing import List, Tuple
from decimal import Decimal
from .order import Order, OrderSide, OrderType, OrderStatus
from .events import TradeEvent, OrderUpdateEvent

class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: List[Order] = []  # Buy orders (sorted highest price first)
        self.asks: List[Order] = []  # Sell orders (sorted lowest price first)

    def add_order(self, order: Order) -> Tuple[List[TradeEvent], List[OrderUpdateEvent]]:
        trades: List[TradeEvent] = []
        updates: List[OrderUpdateEvent] = []

        if order.side == OrderSide.BUY:
            trades, updates = self._match_buy(order)
            if order.status in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]:
                bisect.insort(self.bids, order, key=lambda x: -x.price)
        else:
            trades, updates = self._match_sell(order)
            if order.status in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]:
                bisect.insort(self.asks, order, key=lambda x: x.price)
                
        # Send update for the incoming order as well if it changed or was added
        # If it's fully filled or canceled, its status is already final
        # For simplicity, always send its final status after matching phase
        updates.append(OrderUpdateEvent(
            order_id=order.id,
            status=order.status,
            filled_quantity=order.filled_quantity
        ))

        return trades, updates

    def _execute_trade(self, maker: Order, taker: Order) -> Tuple[TradeEvent, OrderUpdateEvent]:
        # Taker is the incoming order, Maker is the existing order in book
        trade_qty = min(taker.quantity - taker.filled_quantity, maker.quantity - maker.filled_quantity)
        trade_price = maker.price  # Maker always sets the price
        
        trade = TradeEvent(
            symbol=self.symbol,
            maker_order_id=maker.id,
            taker_order_id=taker.id,
            price=trade_price,
            quantity=trade_qty
        )
        
        taker.filled_quantity += trade_qty
        maker.filled_quantity += trade_qty
        
        # Update maker status
        if maker.filled_quantity == maker.quantity:
            maker.status = OrderStatus.FILLED
        else:
            maker.status = OrderStatus.PARTIALLY_FILLED
            
        maker_update = OrderUpdateEvent(
            order_id=maker.id,
            status=maker.status,
            filled_quantity=maker.filled_quantity
        )
        
        # Taker status will be updated at the end of the matching loop
        if taker.filled_quantity == taker.quantity:
            taker.status = OrderStatus.FILLED
        else:
            taker.status = OrderStatus.PARTIALLY_FILLED

        return trade, maker_update

    def _match_buy(self, buy_order: Order) -> Tuple[List[TradeEvent], List[OrderUpdateEvent]]:
        trades = []
        updates = []
        
        while self.asks and buy_order.filled_quantity < buy_order.quantity:
            best_ask = self.asks[0]
            
            # Check price matching
            if buy_order.order_type == OrderType.LIMIT:
                if best_ask.price > buy_order.price:
                    break  # Buy order price is too low
            
            # Execute trade
            trade, maker_update = self._execute_trade(best_ask, buy_order)
            trades.append(trade)
            updates.append(maker_update)
            
            # Remove filled maker from book
            if best_ask.status == OrderStatus.FILLED:
                self.asks.pop(0)
                
        # If MARKET order and still unfilled, cancel the rest
        if buy_order.order_type == OrderType.MARKET and buy_order.filled_quantity < buy_order.quantity:
            # If nothing matched, maybe it was just added? Status becomes canceled
            buy_order.status = OrderStatus.CANCELED
            
        return trades, updates

    def _match_sell(self, sell_order: Order) -> Tuple[List[TradeEvent], List[OrderUpdateEvent]]:
        trades = []
        updates = []
        
        while self.bids and sell_order.filled_quantity < sell_order.quantity:
            best_bid = self.bids[0]
            
            # Check price matching
            if sell_order.order_type == OrderType.LIMIT:
                if best_bid.price < sell_order.price:
                    break  # Sell order price is too high
                    
            # Execute trade
            trade, maker_update = self._execute_trade(best_bid, sell_order)
            trades.append(trade)
            updates.append(maker_update)
            
            # Remove filled maker from book
            if best_bid.status == OrderStatus.FILLED:
                self.bids.pop(0)
                
        # If MARKET order and still unfilled, cancel the rest
        if sell_order.order_type == OrderType.MARKET and sell_order.filled_quantity < sell_order.quantity:
            sell_order.status = OrderStatus.CANCELED
            
        return trades, updates

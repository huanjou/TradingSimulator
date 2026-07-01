from typing import List
from .order import Order, OrderSide
from .trade import Trade

class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: List[Order] = []  # Buy orders (sorted highest price first)
        self.asks: List[Order] = []  # Sell orders (sorted lowest price first)
        
    def add_order(self, order: Order) -> List[Trade]:
        trades = []
        
        if order.side == OrderSide.BUY:
            trades = self._match_buy(order)
            if order.quantity > 0:
                self.bids.append(order)
                # Sort descending by price. Python's stable sort preserves time priority.
                self.bids.sort(key=lambda x: x.price, reverse=True)
        else:
            trades = self._match_sell(order)
            if order.quantity > 0:
                self.asks.append(order)
                # Sort ascending by price. Python's stable sort preserves time priority.
                self.asks.sort(key=lambda x: x.price)
                
        return trades

    def _execute_trade(self, maker: Order, taker: Order) -> Trade:
        trade_qty = min(taker.quantity, maker.quantity)
        trade = Trade(
            symbol=self.symbol,
            maker_order_id=maker.id,
            taker_order_id=taker.id,
            price=maker.price,  # Maker always sets the price
            quantity=trade_qty
        )
        
        taker.quantity -= trade_qty
        maker.quantity -= trade_qty
        return trade

    def _match_buy(self, buy_order: Order) -> List[Trade]:
        trades = []
        # Match against asks
        while self.asks and buy_order.quantity > 0:
            best_ask = self.asks[0]
            if best_ask.price > buy_order.price:
                break  # Buy order price is too low to match
            
            trade = self._execute_trade(maker=best_ask, taker=buy_order)
            trades.append(trade)
            
            if best_ask.quantity == 0:
                self.asks.pop(0)
                
        return trades

    def _match_sell(self, sell_order: Order) -> List[Trade]:
        trades = []
        # Match against bids
        while self.bids and sell_order.quantity > 0:
            best_bid = self.bids[0]
            if best_bid.price < sell_order.price:
                break  # Sell order price is too high to match
            
            trade = self._execute_trade(maker=best_bid, taker=sell_order)
            trades.append(trade)
            
            if best_bid.quantity == 0:
                self.bids.pop(0)
                
        return trades

from typing import Dict, List, Tuple
from .order import Order
from .order_book import OrderBook
from .events import TradeEvent, OrderUpdateEvent

class MatchingEngine:
    def __init__(self):
        self.order_books: Dict[str, OrderBook] = {}

    def process_order(self, order: Order) -> Tuple[List[TradeEvent], List[OrderUpdateEvent]]:
        if order.symbol not in self.order_books:
            self.order_books[order.symbol] = OrderBook(symbol=order.symbol)

        book = self.order_books[order.symbol]
        trades, updates = book.add_order(order)

        return trades, updates

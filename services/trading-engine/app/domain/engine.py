from typing import Dict, List
from .order import Order
from .order_book import OrderBook
from .trade import Trade

class MatchingEngine:
    def __init__(self):
        self.order_books: Dict[str, OrderBook] = {}
        
    def process_order(self, order: Order) -> List[Trade]:
        if order.symbol not in self.order_books:
            self.order_books[order.symbol] = OrderBook(symbol=order.symbol)
            
        book = self.order_books[order.symbol]
        trades = book.add_order(order)
        
        return trades

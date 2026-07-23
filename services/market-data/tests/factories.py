import factory
from app.domain.models import MarketEvent


class MarketEventFactory(factory.Factory):
    class Meta:
        model = MarketEvent

    symbol = "BTC/USD"
    bid_price = 50000.0
    ask_price = 50001.0
    timestamp = 1625097600000


class BinanceDataFactory(factory.DictFactory):
    e = "aggTrade"
    s = "BTCUSDT"
    p = "50000.0"
    q = "1.5"
    T = 1625097600000


class BinancePayloadFactory(factory.DictFactory):
    stream = "btcusdt@aggTrade"
    data = factory.SubFactory(BinanceDataFactory)

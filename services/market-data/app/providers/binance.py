import asyncio
import json
from typing import AsyncIterable, List

import structlog
import websockets
from app.domain.models import MarketEvent
from app.providers.base import MarketDataProvider

logger = structlog.get_logger(__name__)


class BinanceMarketDataProvider(MarketDataProvider):
    """
    Connects to Binance WebSocket API to stream order book tickers.
    Supports multiple symbols.
    """

    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.ws_url = self._build_ws_url()
        self._ws = None

    def _build_ws_url(self) -> str:
        streams = []
        for sym in self.symbols:
            # "BTC/USD" -> "btcusdt"
            formatted_sym = sym.replace("/", "").replace("-", "").lower()
            if not formatted_sym.endswith("usdt"):
                formatted_sym = formatted_sym.replace("usd", "usdt")
            streams.append(f"{formatted_sym}@bookTicker")

        # Single stream vs Combined stream
        if len(streams) == 1:
            return f"wss://stream.binance.com:9443/ws/{streams[0]}"

        streams_joined = "/".join(streams)
        return f"wss://stream.binance.com:9443/stream?streams={streams_joined}"

    def _parse_symbol(self, binance_symbol: str) -> str:
        s = binance_symbol.upper()
        if s.endswith("USDT"):
            return s[:-4] + "/USD"
        return s

    async def add_symbol(self, symbol: str):
        if symbol in self.symbols:
            return

        self.symbols.append(symbol)
        if self._ws:
            formatted_sym = symbol.replace("/", "").replace("-", "").lower()
            if not formatted_sym.endswith("usdt"):
                formatted_sym = formatted_sym.replace("usd", "usdt")
            stream_name = f"{formatted_sym}@bookTicker"

            payload = {
                "method": "SUBSCRIBE",
                "params": [stream_name],
                "id": len(self.symbols),
            }
            await self._ws.send(json.dumps(payload))
            logger.info(
                "Sent dynamic SUBSCRIBE command to Binance",
                symbol=symbol,
                stream=stream_name,
            )

    async def stream_prices(self) -> AsyncIterable[MarketEvent]:
        while True:
            try:
                # Always connect to combined stream endpoint for dynamic subscriptions
                ws_url = "wss://stream.binance.com:9443/stream"
                async with websockets.connect(ws_url) as ws:
                    self._ws = ws
                    logger.info("Connected to Binance WebSocket", url=ws_url)

                    # Initial subscribe
                    streams = []
                    for sym in self.symbols:
                        formatted_sym = sym.replace("/", "").replace("-", "").lower()
                        if not formatted_sym.endswith("usdt"):
                            formatted_sym = formatted_sym.replace("usd", "usdt")
                        streams.append(f"{formatted_sym}@bookTicker")

                    if streams:
                        await ws.send(
                            json.dumps(
                                {"method": "SUBSCRIBE", "params": streams, "id": 1}
                            )
                        )

                    async for message in ws:
                        payload = json.loads(message)

                        # If combined stream, data is nested
                        if "data" in payload:
                            data = payload["data"]
                        else:
                            # Ignore subscribe acks
                            if "result" in payload:
                                continue
                            data = payload

                        # Make sure we actually have data fields
                        if "s" not in data or "b" not in data or "a" not in data:
                            continue

                        symbol = self._parse_symbol(data.get("s", ""))
                        bid_price = float(data.get("b", 0))
                        ask_price = float(data.get("a", 0))
                        timestamp = data.get("E", 0)

                        yield MarketEvent(
                            symbol=symbol,
                            bid_price=bid_price,
                            ask_price=ask_price,
                            timestamp=timestamp,
                        )
            except asyncio.CancelledError:
                logger.info("Binance provider stopping...")
                raise
            except Exception as e:
                logger.error(
                    "WebSocket connection error. Reconnecting...", error=str(e)
                )
                await asyncio.sleep(5)

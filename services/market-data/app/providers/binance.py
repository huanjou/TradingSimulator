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

    def _format_stream_name(self, symbol: str) -> str:
        formatted_sym = symbol.replace("/", "").replace("-", "").lower()
        if not formatted_sym.endswith("usdt"):
            formatted_sym = formatted_sym.replace("usd", "usdt")
        return f"{formatted_sym}@bookTicker"

    def _build_ws_url(self) -> str:
        streams = [self._format_stream_name(sym) for sym in self.symbols]
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
            stream_name = self._format_stream_name(symbol)

            payload = {
                "method": "SUBSCRIBE",
                "params": [stream_name],
                "id": len(self.symbols),
            }
            try:
                await self._ws.send(json.dumps(payload))
                logger.info(
                    "Sent dynamic SUBSCRIBE command to Binance",
                    symbol=symbol,
                    stream=stream_name,
                )
            except websockets.exceptions.ConnectionClosed:
                logger.warning(
                    "Could not send dynamic SUBSCRIBE: WebSocket is closed.",
                    symbol=symbol,
                )

    async def close(self):
        if self._ws:
            await self._ws.close()
            logger.info("Binance WebSocket provider closed gracefully")

    async def stream_prices(self) -> AsyncIterable[MarketEvent]:
        retry_delay = 1.0
        max_delay = 60.0
        while True:
            try:
                # Always connect to combined stream endpoint for dynamic subscriptions
                ws_url = "wss://stream.binance.com:9443/stream"
                async with websockets.connect(ws_url) as ws:
                    self._ws = ws
                    retry_delay = 1.0  # Reset backoff on successful connect
                    logger.info("Connected to Binance WebSocket", url=ws_url)

                    # Initial subscribe
                    streams = [self._format_stream_name(sym) for sym in self.symbols]

                    if streams:
                        await ws.send(
                            json.dumps(
                                {"method": "SUBSCRIBE", "params": streams, "id": 1}
                            )
                        )

                    async for message in ws:
                        try:
                            payload = json.loads(message)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Received invalid JSON from Binance", message=message
                            )
                            continue

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
                    f"WebSocket connection error. Reconnecting in {retry_delay}s...",
                    error=str(e),
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)

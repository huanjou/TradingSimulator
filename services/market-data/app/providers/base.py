from abc import ABC, abstractmethod
from typing import AsyncIterable

from app.domain.models import MarketEvent


class MarketDataProvider(ABC):
    @abstractmethod
    async def stream_prices(self) -> AsyncIterable[MarketEvent]:
        """Streams market events from the provider."""
        pass

    @abstractmethod
    async def add_symbol(self, symbol: str):
        """Dynamically add a symbol to the existing stream."""
        pass

import asyncio
from abc import ABC, abstractmethod

class SchwabHubProvider(ABC):
    """
    Base class for Schwab Hub providers (schwab-py or schwabdev).
    """
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize authentication and clients."""
        pass

    @abstractmethod
    async def start_stream(self, symbols_l1: list[str] = None, symbols_l2: list[str] = None, on_message_cb=None):
        """Start the WebSocket stream."""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the stream."""
        pass

    @abstractmethod
    async def execute_rest(self, method: str, params: dict) -> dict:
        """Execute a REST request."""
        pass

    @abstractmethod
    async def resolve_futures_symbols(self, root_symbols: list[str]) -> dict[str, str]:
        """Resolve root symbols (e.g. /ES) to actual active contracts (e.g. /ESM26)."""
        pass

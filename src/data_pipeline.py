"""Data pipeline with ccxt.pro multi-exchange streaming.

This module exposes :class:`DataPipeline` which can watch OHLCV candles
from multiple exchanges concurrently using ``ccxt.pro`` WebSockets.
Incoming candles are placed into a standard :class:`queue.Queue` for
consumption by other parts of the application such as the GUI.
"""
from __future__ import annotations

import asyncio
import logging
import queue
from typing import Dict, List, Tuple

try:  # pragma: no cover - optional dependency
    import ccxt.pro as ccxtpro
except Exception:  # fallback stub for environments without ccxt.pro
    class ccxtpro:  # type: ignore
        pass

logger = logging.getLogger(__name__)


class DataPipeline:
    """Stream OHLCV data from multiple exchanges."""

    def __init__(self, exchanges: List[str], symbol: str, timeframe: str = "1m") -> None:
        self.exchanges = exchanges
        self.symbol = symbol
        self.timeframe = timeframe
        self.data_queue: "queue.Queue[Tuple[str, list]]" = queue.Queue()
        self._clients: Dict[str, object] = {}

    async def _get_client(self, name: str) -> object:
        """Return a cached ccxt.pro client for ``name``."""
        if name not in self._clients:
            logger.debug("initializing ccxt.pro client for %s", name)
            exchange_class = getattr(ccxtpro, name)
            self._clients[name] = exchange_class()
        return self._clients[name]

    async def _watch_ohlcv(self, name: str) -> None:
        """Internal task to stream candles for ``name``."""
        client = await self._get_client(name)
        while True:
            try:
                candles = await client.watch_ohlcv(self.symbol, self.timeframe)
                if candles:
                    self.data_queue.put((name, candles[-1]))
                    logger.debug("streamed candle from %s", name)
            except Exception as exc:  # pragma: no cover - network errors
                logger.warning("stream error from %s: %s", name, exc)
                await asyncio.sleep(5)

    async def stream(self) -> None:
        """Start streaming on all configured exchanges."""
        await asyncio.gather(*(self._watch_ohlcv(name) for name in self.exchanges))

    async def close(self) -> None:
        """Close all open ccxt.pro clients."""
        for client in self._clients.values():
            try:
                await client.close()
            except Exception:
                pass
        self._clients.clear()

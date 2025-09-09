import asyncio
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from loguru import logger
import ccxt.pro as ccxtpro
from src.utils.ohlcv import to_dataframe
import queue

class DataPipeline:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.live_frames = {}
        self.exchange_client = None

    async def _get_client(self, exchange_name: str):
        if self.exchange_client and getattr(self.exchange_client, "id", None) == exchange_name:
            return self.exchange_client
        if self.exchange_client:
            await self.exchange_client.close()
        logger.info(f"Initializing ccxt.pro client for {exchange_name}")
        exchange_class = getattr(ccxtpro, exchange_name)
        self.exchange_client = exchange_class()
        return self.exchange_client

    async def fetch_historical(self, exchange_name: str, symbol: str, timeframe: str = "1m", limit: int = 500):
        ex = await self._get_client(exchange_name)
        try:
            ohlcv = await ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        finally:
            pass  # Keep client open for streaming
        df = to_dataframe(ohlcv)
        self.cache_parquet(f"{exchange_name}_{symbol}_{timeframe}", df)
        return df

    async def stream_ohlcv(self, exchange_name: str, symbol: str, timeframe: str, data_queue: queue.Queue):
        client = await self._get_client(exchange_name)
        logger.info(f"Starting WebSocket stream for {symbol} on {exchange_name}...")
        while True:
            try:
                candles = await client.watch_ohlcv(symbol, timeframe)
                if candles:
                    df = to_dataframe(candles)
                    data_queue.put(df)
                    logger.debug(f"Streamed {len(df)} new candle(s) for {symbol}")
            except Exception as e:
                logger.error(f"WebSocket stream error for {symbol}: {e}. Reconnecting in 10s...")
                await asyncio.sleep(10)
                await self.close()
                client = await self._get_client(exchange_name)

    def cache_parquet(self, key: str, df: pd.DataFrame):
        path = self.cache_dir / f"{key}.parquet"
        table = pa.Table.from_pandas(df)
        pq.write_table(table, path)
        logger.info({"event": "cache_parquet", "path": str(path), "rows": len(df)})
        return path

    async def close(self):
        if self.exchange_client:
            logger.warning(f"Closing WebSocket client for {self.exchange_client.id}")
            await self.exchange_client.close()
            self.exchange_client = None


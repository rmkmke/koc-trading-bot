import asyncio
import types
import pytest
import sys
from pathlib import Path

# Ensure src package is importable
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

import data_pipeline as dp_mod

# Provide stub ccxt.pro if missing
if not hasattr(dp_mod, "ccxtpro"):
    dp_mod.ccxtpro = types.SimpleNamespace()

DataPipeline = dp_mod.DataPipeline


class DummyExchange:
    def __init__(self):
        self.id = "dummy"

    async def watch_ohlcv(self, symbol, timeframe):
        await asyncio.sleep(0)
        return [[0, 1, 2, 3, 4, 5]]

    async def close(self):
        pass


def test_multi_exchange_stream(monkeypatch):
    monkeypatch.setattr(dp_mod.ccxtpro, "dummy", DummyExchange, raising=False)
    dp = DataPipeline(["dummy"], "BTC/USDT")

    async def run_once():
        task = asyncio.create_task(dp._watch_ohlcv("dummy"))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_once())
    assert not dp.data_queue.empty()

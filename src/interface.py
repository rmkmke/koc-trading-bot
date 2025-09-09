"""Minimal GUI showing aggregated OHLCV data in a mini-chart.

The :class:`MiniChart` class consumes data from :class:`DataPipeline` and
renders the last close price from multiple exchanges using matplotlib.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Tuple

import matplotlib
matplotlib.use("Agg")  # use non-interactive backend for safety
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd

from .data_pipeline import DataPipeline


class MiniChart:
    """Display aggregated close prices from multiple exchanges."""

    def __init__(self, pipeline: DataPipeline) -> None:
        self.pipeline = pipeline
        self.df = pd.DataFrame()
        self.fig, self.ax = plt.subplots(figsize=(5, 3))

    def start(self) -> None:
        """Start the data pipeline and render the chart."""
        thread = threading.Thread(target=lambda: asyncio.run(self.pipeline.stream()), daemon=True)
        thread.start()
        self.ani = FuncAnimation(self.fig, self._update, interval=1000)
        plt.show()

    def _update(self, _frame: int) -> None:
        q = self.pipeline.data_queue
        updated = False
        while not q.empty():
            exchange, candle = q.get()
            ts, _o, _h, _l, close, _v = candle
            idx = pd.to_datetime(ts, unit="ms")
            self.df.loc[idx, exchange] = close
            updated = True
        if updated:
            self.ax.clear()
            self.df.plot(ax=self.ax)
            self.ax.set_xlabel("time")
            self.ax.set_ylabel("close")
            self.ax.set_title(self.pipeline.symbol)

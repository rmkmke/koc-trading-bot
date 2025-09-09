"""Example entry point demonstrating the mini-chart with aggregated streams."""
from __future__ import annotations

from .data_pipeline import DataPipeline
from .interface import MiniChart


def main() -> None:
    pipeline = DataPipeline(["binance", "kraken"], "BTC/USDT")
    chart = MiniChart(pipeline)
    chart.start()


if __name__ == "__main__":
    main()

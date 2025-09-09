from loguru import logger
import pandas as pd
import vectorbt as vbt


class Backtester:
    def run_vectorized(self, data, params):
        logger.info({
            "event": "backtest_vectorized",
            "params": params,
            "rows": int(len(getattr(data, "index", [])))
        })

        close = data["close"].astype(float)
        strategy = params.get("strategy", "momentum")
        window = int(params.get("window", 14))
        init_cash = float(params.get("init_cash", 10_000))
        fees = float(params.get("fees", 0.0))
        size = float(params.get("size", 1.0))

        entries = params.get("entries")
        exits = params.get("exits")

        if entries is None or exits is None:
            if strategy == "rsi":
                rsi = vbt.RSI.run(close, window=window).rsi
                entries = rsi < 30
                exits = rsi > 70
            elif strategy == "sma":
                fast = vbt.MA.run(close, window=max(2, window // 2)).ma
                slow = vbt.MA.run(close, window=window).ma
                entries = (fast > slow) & (fast.shift(1) <= slow.shift(1))
                exits = (fast < slow) & (fast.shift(1) >= slow.shift(1))
            else:  # momentum fallback
                diff = close.diff().fillna(0)
                entries = diff > 0
                exits = diff < 0

        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            init_cash=init_cash,
            fees=fees,
            size=size,
        )

        # Collect a compact set of stats for GUI
        stats = pf.stats()
        try:
            sharpe = float(stats.get("Sharpe Ratio", 0.0))
        except Exception:
            sharpe = float(pf.sharpe_ratio())
        result = {
            "sharpe": sharpe,
            "total_return": float(pf.total_return()),
            "trades": int(getattr(pf.trades, "count", 0)),
        }
        # Also include equity series for plotting
        result["equity"] = pf.get_total_value().rename("equity")
        return result

    def run_event_driven(self, data, params):
        logger.info({
            "event": "backtest_event",
            "params": params,
            "rows": int(len(getattr(data, "index", [])))
        })
        # Placeholder for event-driven simulation
        return {"drawdown": 0.0, "wins": 0, "losses": 0}

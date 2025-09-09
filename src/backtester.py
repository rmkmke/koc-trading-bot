from loguru import logger
import vectorbt as vbt


class Backtester:
    def run_vectorized(self, data, params):
        logger.info({"event": "backtest_vectorized", "params": params, "rows": len(getattr(data, "index", []))})
        # Placeholder: build simple signals if not provided
        entries = params.get("entries")
        exits = params.get("exits")
        if entries is None or exits is None:
            # naive momentum: enter when close rises, exit when falls
            close = data["close"].astype(float)
            diff = close.diff().fillna(0)
            entries = diff > 0
            exits = diff < 0
        pf = vbt.Portfolio.from_signals(
            data["close"].astype(float), entries=entries, exits=exits, init_cash=params.get("init_cash", 10000)
        )
        return {"sharpe": float(pf.sharpe_ratio()), "pnl": float(pf.total_return())}

    def run_event_driven(self, data, params):
        logger.info({"event": "backtest_event", "params": params, "rows": len(getattr(data, "index", []))})
        # Placeholder for event-driven simulation
        return {"drawdown": 0.0, "wins": 0, "losses": 0}


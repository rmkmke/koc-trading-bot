# K.O.C. v0.1.0 – Initial Scaffold

Highlights
- Event-driven asyncio core, warnings-over-enforcement with loguru JSON logs.
- Live OHLCV streaming via ccxt.pro, matplotlib GUI mini-chart + mascot.
- Dynamic plugin processes with ZeroMQ telemetry (PnL, trades/hour).
- Vectorbt backtesting stub; Parquet caching and OHLCV validation.
- Keyring/YAML/Docker secrets config; GUI start/stop, backtest, deploy controls.

Install
- See README for virtualenv-first setup and config guidance.

Notes
- Prefer testnet/paper accounts during development.
- Backtesting suite and multi-stream aggregation planned next.

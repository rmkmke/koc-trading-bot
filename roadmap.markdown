# K.O.C. Development Roadmap

## Phase 1: Foundation (Complete)
- [x] Initialize repository: `koc-trading-bot/` with `src/`, `strategies/`, `tests/`, `data_cache/`, `logs/`, `configs/`, `requirements.txt`, `README.md`, `main.py`, `Dockerfile`.
- [x] Configure `.gitignore`: Ignore `logs/`, `data_cache/`, `__pycache__/`, `configs/`.
- [x] Define `requirements.txt`: Include `matplotlib`, `pyzmq`, `ccxt-pro`.
- [x] Test dependencies on Windows/Ubuntu/macOS (virtualenv).
- [x] Implement `config.py`: `keyring` and `/run/secrets/` support.
- [x] Commit initial setup.

## Phase 2: Data & Latency
- [x] Implement `logger.py`: JSON logs with `loguru`.
- [x] Implement `resilience.py`: `tenacity` retries, `pybreaker` circuit breakers.
- [x] Enhance `config.py`: Account switching for all venues.
- [x] Implement `data_pipeline.py`: `ccxt.pro` streaming, `validate_ohlcv`, Parquet caching.
- [x] Implement `interface.py`: `matplotlib` chart, metrics, mascot, deploy buttons.
- [x] Implement `telemetry.py`: ZeroMQ SUB for plugin heartbeats/metrics.
- [ ] Extend `api_manager.py`: Add KuCoin/Bitfinex rate limit parsing.
- [ ] Enhance `data_pipeline.py`: Aggregate multiple `ccxt.pro` WebSocket streams.

## Phase 3: Strategy & Backtests
- [ ] Implement `backtester.py`: Full `vectorbt` sweeps, `Backtrader` simulator.
- [ ] Enhance sample plugins: Real logic for `scalping.py`, `arbitrage.py`.
- [ ] Implement `scheduler.py`: Schedule plugin execution.

## Phase 4: Testing & Validation
- [ ] Write `tests/test_streaming.py`: Test WebSocket and queue.
- [ ] Write `tests/test_gui.py`: Test chart, metrics, and controls.
- [ ] Manually test GUI: Streaming, account switching, backtesting, deployment.
- [ ] Optimize latency (<500ms) and WebSocket reconnection.
- [ ] Test cross-platform: Windows, Ubuntu, macOS, Docker.

## Phase 5: Deployment & Polish
- [ ] Deploy: Virtualenv and Docker.
- [ ] Add plugins: `strategies/pairs_trading.py`.
- [ ] Document: Update `README.md`, inline comments, user guide.
- [ ] Push to repository.

## Next Steps
- [ ] Integrate `vectorbt` backtesting with historical data and GUI params.
- [ ] Implement full order execution in `api_manager.py`.
- [ ] Enhance `data_pipeline.py` with multi-stream `ccxt.pro` aggregation.
- [ ] Test KuCoin/Bitfinex connectivity.
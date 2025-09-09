# ⚔️ Grok’s K.O.C. (Killer Operations Core)

## Purpose
Grok’s K.O.C. is a **freedom-first**, production-grade trading bot foundation for traders prioritizing performance and control. Built on an event-driven `asyncio` core, K.O.C. delivers **sub-500ms** trade execution and **live OHLCV streaming** via `ccxt.pro` WebSockets across Binance, Kraken, Coinbase, Alpaca, Polygon.io, Yahoo Finance, KuCoin, and Bitfinex, with seamless account switching (e.g., Alpaca paper/live, Binance testnet/live). Its **dynamic plugin system** loads strategies from `strategies/`, running unrestricted in sandboxed processes with ZeroMQ telemetry for metrics (PnL, trades/hour). The `customtkinter` GUI features a `matplotlib` mini-chart for real-time OHLCV, strategy metrics, and a **gigapet-style mascot** (🤖/💃/😔) tied to performance. K.O.C. emphasizes **virtualenv** deployment (Windows 11, Ubuntu 22.04+, macOS), with Docker optional, and logs warnings via `loguru` without enforcement.

## Objectives
- **Unified API Management**: Securely manages Binance, Kraken, Coinbase, Alpaca, Polygon.io, Yahoo Finance, KuCoin, Bitfinex APIs with `keyring` and rate limiting.
- **Robust Plugin System**: Dynamic loading from `strategies/`, GUI-configurable JSON params, integrated with trading/backtesting.
- **Flawless Connectivity**: <500ms trades, circuit breakers for API errors (e.g., 401, 429), WebSocket reconnection.
- **Strategy-Agnostic Core**: Event-driven, no restrictive safeties unless added as plugins.
- **Enhanced GUI**: Controls for start/stop, backtest, API keys, plugin install, deploy (Windows/Ubuntu/Docker), with real-time OHLCV chart and metrics.
- **Extensible Data**: Polygon.io, Yahoo Finance, Alpaca, Binance, Kraken, Coinbase for OHLCV, with Parquet caching and `ccxt.pro` streaming.
- **Hybrid Backtesting**: `vectorbt` for speed, `Backtrader` for fidelity, GUI-triggered with plugin params.
- **Flexible Deployment**: Virtualenv-first (Windows/Ubuntu/macOS), Docker optional.
- **Thorough Testing**: Verifies API connectivity, plugin execution, latency, and GUI.

## Requirements
- **Python**: 3.10+
- **Dependencies** (in `requirements.txt`):
  ```
  alpaca-py>=0.13.1
  ccxt>=4.3.0
  ccxt-pro>=2.6.45
  polygon-api-client>=1.14.0
  yfinance>=0.2.40
  python-binance>=1.0.19
  pykrakenapi>=0.1.8
  coinbase>=2.3.0
  pyzmq>=26.0.3
  vectorbt>=0.26.2
  backtrader>=1.9.78
  pandas>=2.2.2
  pyarrow>=16.1.0
  apscheduler>=3.10.4
  tenacity>=8.4.0
  pybreaker>=1.0.0
  loguru>=0.7.2
  keyring>=25.3.0
  customtkinter>=5.2.2
  matplotlib>=3.9.0
  pytest>=8.3.2
  pytest-asyncio>=0.23.8
  ```
- **OS**: Windows 11, Ubuntu 22.04+, macOS (Docker optional).
- **API Keys**: Use testnet/paper accounts for testing (Binance testnet, Alpaca paper, etc.).

## Quickstart (Virtualenv-First)
```bash
git clone <repo-url> && cd koc-trading-bot
python -m venv venv
# Windows: venv\Scripts\activate
# Unix/macOS: source venv/bin/activate
pip install -r requirements.txt
cp configs/accounts.yaml.example configs/accounts.yaml
python src/main.py
```
 - **Config**: Prefer OS `keyring` (`koc:<name>:apiKey`, `koc:<name>:secret`); fallback to `configs/accounts.yaml` or `/run/secrets/` (Docker, set `KOC_DOCKER=1`).
- **GUI**: Start/stop streaming, switch accounts, install plugins, run backtests, deploy, view OHLCV chart, metrics, and mascot.
- **Headless**: Runs without GUI if `customtkinter` unavailable.

## Usage
- **GUI Dashboard**:
  - **Controls**: Start/stop streaming, switch accounts (e.g., Alpaca paper/live), install plugins, run backtests, deploy (Windows/Ubuntu/Docker).
  - **Displays**: Live BTC/USDT OHLCV mini-chart, strategy metrics (PnL, trades/hour), logs, JSON params.
  - **Mascot**: Emoji-based 🤖/💃/😔 animations tied to PnL or manual toggle.
- **Plugins**: Add to `strategies/` (e.g., `scalping.py`). Sandboxed with ZeroMQ heartbeats.
- **Streaming**: Live OHLCV via `ccxt.pro` WebSocket, displayed in GUI chart.
- **Backtesting**: Hybrid (`vectorbt` sweeps, `Backtrader` event-driven), GUI-triggered.
- **Deployment**: Virtualenv or Docker (optional).

## Troubleshooting
- **ccxt.pro WebSocket**: Use testnet/paper keys; check `logs/koc.json` for `order_latency_high` or reconnect warnings. Increase retry tolerance in `src/resilience.py` if connections flap.
- **Headless GUI**: If `customtkinter` or display is unavailable, the app runs headless. On Ubuntu servers, use `xvfb` and set `DISPLAY`.
- **Windows Keyring**: Ensure keyring backend is available. Verify entries in Windows Credential Manager under `koc:<name>:apiKey` and `koc:<name>:secret`.

## Configuration
- **Keyring labels**: The code reads credentials from the OS keyring service named `koc` with keys `koc:<name>:apiKey` and `koc:<name>:secret` (e.g., `koc:binance:apiKey`).
- **YAML fallback**: Copy `configs/accounts.yaml.example` to `configs/accounts.yaml` and fill `apiKey`/`secret`. These are overridden by keyring entries when present.
- **Docker secrets**: When `KOC_DOCKER=1`, the loader reads `/run/secrets/<name>_apiKey` and `/run/secrets/<name>_secret` if available.
- **Account modes**: Use `account: testnet|live` for Binance, `account: paper|live` for Alpaca.

## Repo Structure
- `src/`: Core modules (`logger.py`, `resilience.py`, `config.py`, `api_manager.py`, `data_pipeline.py`, `telemetry.py`, `plugins.py`, `scheduler.py`, `backtester.py`, `main.py`, `interface.py`).
- `strategies/`: Example strategy plugins (`scalping.py`, `arbitrage.py`).
- `configs/`: `accounts.yaml.example` (copy to `accounts.yaml`).
- `logs/`: JSON logs (`koc.json`).
- `data_cache/`: Parquet caches for OHLCV.
- `tests/`: Smoke and latency tests.

## Testing
- Run `pytest -q` after installing requirements. For async tests, the suite uses `pytest-asyncio`.


## Development Guidelines
- Use async I/O (`asyncio`) for streaming/trades.
- Sandbox plugins with `multiprocessing` and ZeroMQ; warn on risks (e.g., `logger.warning({"event": "plugin_heartbeat_anomaly", "dt": dt})`).
- Track rate limits per venue (e.g., Binance weight, KuCoin limits).
- Test with `pytest --asyncio-mode=auto` using testnet/paper accounts.
- Log to `logs/koc.json` with `loguru`.

## Support
- Issues: `<repo-url>/issues`
- License: MIT

## Legal
Use testnet/paper accounts during development. You are responsible for exchange TOS compliance.

## Completion Checklist
- [ ] Repo Setup: `git init`, structure, `.gitignore`, commit
- [ ] Dependencies: Install `requirements.txt`
- [ ] Accounts Configured: `keyring`, YAML, or `/run/secrets/`
- [ ] Strategy Plugin: Add to `strategies/`
- [ ] GUI Runs: Headless fallback if no `customtkinter`
- [ ] WebSocket Streams: `ccxt.pro` wired
- [ ] Order Path: Benchmarked <500ms
- [ ] Backtests: Validated with `vectorbt`/`Backtrader`
- [ ] Logs: Observed in `logs/koc.json`
- [ ] Deploy: Virtualenv or Docker

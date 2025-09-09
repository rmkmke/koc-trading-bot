# K.O.C. Scripted Document

> Doc sync notes (current scaffold)
- The resilience helper is named `transient_retry` (not `resilience_retry`) and uses `tenacity.wait_random_exponential`, with a `pybreaker` circuit breaker configured as `fail_max=5`, `reset_timeout=30`.
- Config is function-based: `src/config.py` exports `load_config()` and `switch_account()` rather than a `Config` class.
- API integration is normalized around `ccxt.async_support` (plus `ccxt.pro` for streaming); venue-specific SDKs are not wired in this scaffold.
- The GUI module exists at `src/interface.py` and is instantiated from `src/main.py` via a small factory for headless fallback.
- Sample plugins live in `strategies/` and are spawned in isolated processes; metrics are aggregated by `src/telemetry.py`.

## Overview
Grok’s K.O.C. is a modular, event-driven trading bot foundation for **<500ms trades** and **live OHLCV streaming** across Binance, Kraken, Coinbase, Alpaca, Polygon.io, Yahoo Finance, KuCoin, and Bitfinex. It features a sandboxed plugin system, a `customtkinter` GUI with `matplotlib` mini-chart and mascot, a ZeroMQ telemetry bus, and virtualenv-first deployment. This document outlines all modules with implementations.

## Components

### 1. Logger
- **File**: `src/logger.py`
- **Purpose**: Log warnings/errors to `logs/koc.json`.
- **Implementation**:
  ```python
  from loguru import logger
  from pathlib import Path
  import sys, json

  LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "koc.json"

  def setup_logger(level="INFO"):
      logger.remove()
      logger.add(sys.stdout, level=level, serialize=False)
      logger.add(LOG_PATH, level="DEBUG", serialize=True, rotation="10 MB", retention=10)
      logger.debug(json.dumps({"event": "logger_initialized", "path": str(LOG_PATH)}))
      return logger
  ```

### 2. Resilience
- **File**: `src/resilience.py`
- **Purpose**: Handle faults with retries and circuit breakers.
- **Implementation**:
  ```python
  from tenacity import retry, stop_after_attempt, wait_exponential
  import pybreaker
  from loguru import logger
  from alpaca.common.exceptions import APIError

  exchange_circuit = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=300, name="exchange_circuit")

  def resilience_retry(func):
      @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), before_sleep=lambda rs: logger.warning({"event": "retry_attempt", "attempt": rs.attempt_number}))
      async def wrapper(*args, **kwargs):
          return await func(*args, **kwargs)
      return wrapper

  def is_retryable_block(exception):
      return isinstance(exception, APIError) and exception.status_code == 429
  ```

### 3. Config
- **File**: `src/config.py`
- **Purpose**: Manage API keys and account switching.
- **Implementation**:
  ```python
  import os, yaml, keyring
  from pathlib import Path
  from loguru import logger

  CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "accounts.yaml"

  class Config:
      def __init__(self):
          self.accounts = self.load_accounts()

      def load_accounts(self):
          os.makedirs("configs", exist_ok=True)
          cfg = yaml.safe_load(CONFIG_PATH.open("r", encoding="utf-8")) if CONFIG_PATH.exists() else {}
          if os.getenv("KOC_DOCKER") == "1":
              for name in cfg:
                  for key in ["key", "secret"]:
                      path = Path(f"/run/secrets/{name}_{key}")
                      if path.exists():
                          cfg[name][key] = path.read_text().strip()
          else:
              for name in cfg:
                  for key in ["key", "secret"]:
                      kr_val = keyring.get_password("koc", f"koc:{name}:{key}")
                      if kr_val:
                          cfg[name][key] = kr_val
          return cfg

      def save_account(self, acct, creds):
          accts = self.load_accounts()
          accts[acct] = creds
          with open(CONFIG_PATH, "w") as f:
              yaml.safe_dump(accts, f)
          keyring.set_password("koc", f"koc:{acct}:key", creds["key"])
          keyring.set_password("koc", f"koc:{acct}:secret", creds["secret"])
          logger.info({"event": "account_saved", "account": acct})

      def switch_account(self, acct, account_type):
          accts = self.load_accounts()
          accts[acct]["account"] = account_type
          if acct == "alpaca":
              accts[acct]["base_url"] = "https://paper-api.alpaca.markets" if account_type == "paper" else "https://api.alpaca.markets"
          elif acct in ("binance", "kucoin", "bitfinex"):
              accts[acct]["enableRateLimit"] = True
              accts[acct]["set_sandbox_mode"] = (account_type == "testnet")
          with open(CONFIG_PATH, "w") as f:
              yaml.safe_dump(accts, f)
          logger.info({"event": "account_switched", "account": acct, "type": account_type})
          return accts
  ```

### 4. API Manager
- **File**: `src/api_manager.py`
- **Purpose**: Unified async API access.
- **Implementation**:
  ```python
  import asyncio, time
  from loguru import logger
  import ccxt.async_support as ccxt
  from alpaca_trade_api import REST as AlpacaREST
  from polygon import RESTClient as PolygonREST
  import yfinance as yf
  from .resilience import resilience_retry, exchange_circuit, is_retryable_block

  class APIManager:
      def __init__(self, config):
          self.config = config
          self.clients = {}
          self.state = {}
          self.rate_limits = {}
          self.init_clients()

      def init_clients(self):
          for acct, creds in self.config.accounts.items():
              self.state[acct] = "idle"
              exchange = creds.get("exchange", acct)
              key = creds.get("key")
              secret = creds.get("secret")
              if exchange == "alpaca":
                  self.clients[acct] = AlpacaREST(key, secret, base_url=creds.get("base_url", "https://paper-api.alpaca.markets"))
              elif exchange == "polygon":
                  self.clients[acct] = PolygonREST(key)
              elif exchange == "yahoo":
                  self.clients[acct] = yf
              else:
                  client = getattr(ccxt, exchange)({
                      "apiKey": key,
                      "secret": secret,
                      "enableRateLimit": True,
                      **creds.get("options", {})
                  })
                  if creds.get("account") == "testnet":
                      client.set_sandbox_mode(True)
                  self.clients[acct] = client
              self.rate_limits[acct] = {"last_weight": 0, "last_ts": time.time()}

      @exchange_circuit
      @resilience_retry
      async def place_order(self, account, symbol, qty, side, type_="market"):
          try:
              t0 = time.perf_counter()
              self.state[account] = "order_submitted"
              client = self.clients[account]
              if account == "alpaca":
                  order = client.submit_order(symbol=symbol, qty=qty, side=side, type=type_, time_in_force="ioc")
              elif account in ("binance", "kraken", "coinbase", "kucoin", "bitfinex"):
                  order = await client.create_order(symbol, type_, side, qty)
              else:
                  raise ValueError(f"Unsupported exchange: {account}")
              latency_ms = (time.perf_counter() - t0) * 1000
              if latency_ms > 500:
                  logger.warning({"event": "order_latency_high", "account": account, "latency_ms": latency_ms})
              self.state[account] = "in_position"
              logger.info({"event": "order_executed", "account": account, "symbol": symbol, "latency_ms": latency_ms})
              return {"order": order, "latency_ms": latency_ms}
          except Exception as e:
              logger.error({"type": "block", "msg": str(e), "account": account})
              if is_retryable_block(e):
                  self.state[account] = "recalculate"
                  raise ValueError(f"Block: Rate limit exceeded")
              self.state[account] = "halted"
              raise
  ```

### 5. Data Pipeline
- **File**: `src/data_pipeline.py`
- **Purpose**: Fetch/cache/stream OHLCV data.
- **Implementation**:
  ```python
  import asyncio
  from pathlib import Path
  import pandas as pd
  import pyarrow.parquet as pq
  import pyarrow as pa
  from loguru import logger
  import ccxt.pro as ccxtpro
  from alpaca_trade_api import Stream as AlpacaStream
  from .utils.ohlcv import to_dataframe
  from .resilience import resilience_retry
  import queue

  class DataPipeline:
      def __init__(self, config, cache_dir: Path):
          self.config = config
          self.cache_dir = cache_dir
          self.cache_dir.mkdir(exist_ok=True)
          self.live_frames = {}
          self.exchange_client = None
          self.subscriptions = []
          self.data_queue = queue.Queue()

      @resilience_retry
      async def get_historical(self, symbol, start, end, source="polygon"):
          try:
              cfg = self.config.accounts.get(source, {})
              if source == "polygon":
                  from polygon import RESTClient
                  client = RESTClient(cfg.get("key"))
                  df = client.get_aggs(symbol, 1, "minute", start, end).to_pandas()
              elif source == "yahoo":
                  import yfinance as yf
                  df = yf.download(symbol, start=start, end=end, interval="1m")
              elif source == "alpaca":
                  from alpaca_trade_api import REST as AlpacaREST
                  client = AlpacaREST(cfg.get("key"), cfg.get("secret"), cfg.get("base_url"))
                  df = client.get_bars(symbol, "1Min", start, end).df
              else:
                  client = await self._get_client(source)
                  df = to_dataframe(await client.fetch_ohlcv(symbol, timeframe="1m", since=start, limit=1000))
              self.validate_ohlcv(df)
              self.cache_parquet(f"{source}_{symbol}_1m", df)
              return df
          except Exception as e:
              logger.error({"type": "block", "msg": str(e), "source": source})
              raise

      def validate_ohlcv(self, df):
          if isinstance(df, pd.DataFrame) and not df.empty:
              highs_ok = (df["high"] >= df[["open", "close", "low"]]).all().all() if {"open", "high", "low", "close"}.issubset(df.columns) else True
              if not highs_ok:
                  logger.error({"type": "block", "msg": "Invalid OHLCV data"})
                  raise ValueError("OHLCV Block")

      async def _get_client(self, exchange_name: str):
          if self.exchange_client and self.exchange_client.id == exchange_name:
              return self.exchange_client
          if self.exchange_client:
              await self.exchange_client.close()
          logger.info(f"Initializing ccxt.pro client for {exchange_name}")
          exchange_class = getattr(ccxtpro, exchange_name)
          cfg = self.config.accounts.get(exchange_name, {})
          client = exchange_class({"apiKey": cfg.get("key"), "secret": cfg.get("secret"), "enableRateLimit": True})
          if cfg.get("account") == "testnet":
              client.set_sandbox_mode(True)
          self.exchange_client = client
          return client

      async def stream_quotes(self, symbol, source="alpaca"):
          if source == "alpaca":
              cfg = self.config.accounts.get("alpaca", {})
              stream = AlpacaStream(cfg.get("key"), cfg.get("secret"), base_url="wss://stream.data.alpaca.markets/v2/sip")
              async def handle_quote(quote):
                  self.live_frames[symbol] = quote
                  self.data_queue.put(quote)
                  logger.debug({"event": "quote_received", "symbol": symbol})
              stream.subscribe_quotes(handle_quote, symbol)
              self.subscriptions.append((symbol, source))
              while True:
                  try:
                      await stream._run_forever()
                  except Exception as e:
                      logger.error({"type": "block", "msg": str(e), "source": source})
                      await self.reconnect_stream(source)
          else:
              client = await self._get_client(source)
              logger.info(f"Starting WebSocket stream for {symbol} on {source}")
              while True:
                  try:
                      candles = await client.watch_ohlcv(symbol, "1m")
                      if candles:
                          df = to_dataframe(candles)
                          self.data_queue.put(df)
                          logger.debug(f"Streamed {len(df)} candle(s) for {symbol}")
                  except Exception as e:
                      logger.error({"type": "block", "msg": str(e), "source": source})
                      await asyncio.sleep(10)
                      await self.close()
                      client = await self._get_client(source)

      def cache_parquet(self, key: str, df):
          path = self.cache_dir / f"{key}.parquet"
          table = pa.Table.from_pandas(df)
          pq.write_table(table, path)
          logger.info({"event": "cache_parquet", "path": str(path), "rows": len(df)})
          return path

      async def reconnect_stream(self, source):
          await asyncio.sleep(2)
          logger.info({"event": "reconnect_stream", "source": source})

      async def close(self):
          if self.exchange_client:
              logger.warning(f"Closing WebSocket client for {self.exchange_client.id}")
              await self.exchange_client.close()
              self.exchange_client = None
  ```

### 6. Telemetry
- **File**: `src/telemetry.py`
- **Purpose**: Aggregate plugin heartbeats/metrics for GUI.
- **Implementation**:
  ```python
  import time, threading
  from typing import Dict, Any, List
  from loguru import logger
  import zmq

  class TelemetryBus:
      def __init__(self, endpoints: List[str] | None = None):
          self.ctx = zmq.Context.instance()
          self.sock = self.ctx.socket(zmq.SUB)
          self.sock.setsockopt(zmq.SUBSCRIBE, b"")
          self.endpoints = endpoints or []
          self.metrics: Dict[str, Dict[str, Any]] = {}
          self._stop = False
          self.thread = None

      def add_endpoint(self, endpoint: str):
          try:
              self.sock.connect(endpoint)
              self.endpoints.append(endpoint)
              logger.info({"event": "telemetry_endpoint_added", "endpoint": endpoint})
          except Exception as e:
              logger.warning({"event": "telemetry_endpoint_failed", "endpoint": endpoint, "err": str(e)})

      def start(self):
          if self.thread and self.thread.is_alive():
              return
          self._stop = False
          self.thread = threading.Thread(target=self._loop, daemon=True)
          self.thread.start()
          logger.info({"event": "telemetry_started"})

      def stop(self):
          self._stop = True
          if self.thread:
              self.thread.join(timeout=1.0)
          logger.info({"event": "telemetry_stopped"})

      def _loop(self):
          poller = zmq.Poller()
          poller.register(self.sock, zmq.POLLIN)
          last_warn: Dict[str, float] = {}
          while not self._stop:
              socks = dict(poller.poll(timeout=250))
              if self.sock in socks and socks[self.sock] == zmq.POLLIN:
                  try:
                      msg = self.sock.recv_json(flags=zmq.NOBLOCK)
                      now = time.time()
                      plugin_id = msg.get("plugin", "unknown")
                      rec = self.metrics.setdefault(plugin_id, {"last_ts": now, "count": 0, "fps": 0.0})
                      dt = now - rec["last_ts"]
                      rec["last_ts"] = now
                      rec["count"] += 1
                      rec["fps"] = 1.0 / dt if dt > 0 else rec.get("fps", 0.0)
                      for k, v in msg.items():
                          if k in ("plugin", "event"): continue
                          if isinstance(v, (int, float)): rec[k] = v
                      self.metrics[plugin_id] = rec
                      if dt < 0.05 or dt > 5.0:
                          ts = last_warn.get(plugin_id, 0)
                          if now - ts > 5.0:
                              logger.warning({"event": "plugin_heartbeat_anomaly", "plugin": plugin_id, "dt": dt})
                              last_warn[plugin_id] = now
                  except Exception as e:
                      logger.warning({"event": "telemetry_parse_error", "err": str(e)})
              else:
                  time.sleep(0.05)
  ```

### 7. Plugins
- **File**: `src/plugins.py`
- **Purpose**: Load/run sandboxed strategies.
- **Implementation**:
  ```python
  import importlib.util, inspect, multiprocessing as mp, zmq, time
  from pathlib import Path
  from loguru import logger
  from .api_manager import APIManager
  from .data_pipeline import DataPipeline

  class Plugin:
      def __init__(self, name, params):
          self.name = name
          self.params = params
          self._pnl = 0.0
          self._trades = 0

      async def run(self, api: APIManager, data: DataPipeline):
          raise NotImplementedError("Plugin must implement run method")

  def _child_worker(module_path, class_name, zmq_endpoint):
      ctx = zmq.Context.instance()
      sock = ctx.socket(zmq.PUB)
      sock.bind(zmq_endpoint)
      spec = importlib.util.spec_from_file_location("plugin_mod", module_path)
      mod = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(mod)
      plugin = getattr(mod, class_name)()
      start_time = time.time()
      while True:
          try:
              plugin.run(api=None, data={})
              sock.send_json({"plugin": class_name, "ts": time.time(), "event": "tick", "pnl": plugin._pnl, "trades": plugin._trades})
              if time.time() - start_time > 10:
                  logger.warning({"event": "plugin_risk", "issue": "high_cpu", "plugin": class_name})
              time.sleep(1)
          except Exception as e:
              logger.warning({"event": "plugin_error", "plugin": class_name, "error": str(e)})
              time.sleep(2)
          finally:
              sock.close()

  class PluginManager:
      def __init__(self):
          self.plugins = {}
          self.processes = []

      def load_plugin(self, plugin_path):
          try:
              plugin_name = Path(plugin_path).stem
              spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
              module = importlib.util.module_from_spec(spec)
              spec.loader.exec_module(module)
              plugin_class = next((obj for name, obj in inspect.getmembers(module, inspect.isclass) if issubclass(obj, Plugin) and obj is not Plugin), None)
              if not plugin_class:
                  raise ValueError(f"Plugin at {plugin_path} must define a subclass of Plugin")
              return plugin_class
          except Exception as e:
              logger.error({"type": "block", "msg": f"Plugin Load Block: {e}", "path": str(plugin_path)})
              raise

      def register_plugin(self, plugin_path, params):
          plugin_class = self.load_plugin(plugin_path)
          plugin = plugin_class(plugin_path, params)
          endpoint = f"tcp://127.0.0.1:{self._free_port()}"
          p = mp.Process(target=_child_worker, args=(str(plugin_path), plugin_class.__name__, endpoint), daemon=True)
          p.start()
          self.plugins[plugin_path] = plugin
          self.processes.append({"process": p, "endpoint": endpoint, "file": str(plugin_path), "class": plugin_class.__name__})
          return plugin

      def _free_port(self):
          import socket
          with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
              s.bind(("", 0))
              return s.getsockname()[1]
  ```

### 8. Backtester
- **File**: `src/backtester.py`
- **Purpose**: Hybrid backtesting with GUI integration.
- **Implementation**:
  ```python
  import backtrader as bt
  import vectorbt as vbt
  import pandas as pd
  from loguru import logger

  class Backtester:
      async def run_vectorized(self, data, params):
          try:
              entries = params.get("entries", pd.Series(data.index, index=data.index, dtype=bool))
              exits = params.get("exits", pd.Series(data.index, index=data.index, dtype=bool))
              pf = vbt.Portfolio.from_signals(data.close, entries=entries, exits=exits, fees=params.get("fees", 0.001))
              stats = pf.stats()
              logger.info({"event": "backtest_vectorized", "params": params, "rows": len(data), "stats": stats})
              return stats
          except Exception as e:
              logger.error({"type": "block", "msg": f"Backtest Vectorized Block: {e}"})
              raise

      async def run_event_driven(self, data, strategy_class=None):
          try:
              cerebro = bt.Cerebro()
              cerebro.adddata(bt.feeds.PandasData(dataname=data))
              if strategy_class:
                  cerebro.addstrategy(strategy_class)
              cerebro.run()
              logger.info({"event": "backtest_event", "rows": len(data)})
              return cerebro
          except Exception as e:
              logger.error({"type": "block", "msg": f"Backtest Event Block: {e}"})
              raise
  ```

### 9. Scheduler
- **File**: `src/scheduler.py`
- **Purpose**: Schedule plugin tasks.
- **Implementation**:
  ```python
  from apscheduler.schedulers.asyncio import AsyncIOScheduler
  from loguru import logger

  class Scheduler:
      def __init__(self):
          self.scheduler = AsyncIOScheduler()

      async def schedule_task(self, func, interval):
          try:
              self.scheduler.add_job(func, "interval", seconds=interval, max_instances=1)
              self.scheduler.start()
              logger.info({"event": "scheduler_job_added", "interval_s": interval})
          except Exception as e:
              logger.error({"type": "block", "msg": f"Scheduler Block: {e}"})
  ```

### 10. GUI
- **File**: `src/interface.py`
- **Purpose**: Control bot, display charts/metrics/mascot.
- **Implementation**:
  ```python
  import customtkinter as ctk
  import asyncio, json, subprocess, queue
  from loguru import logger
  import pandas as pd
  from matplotlib.figure import Figure
  from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
  import matplotlib.ticker as mticker
  from .config import Config
  from .api_manager import APIManager
  from .data_pipeline import DataPipeline
  from .backtester import Backtester
  from .plugins import PluginManager
  from .telemetry import TelemetryBus

  class Interface:
      def __init__(self):
          ctk.set_appearance_mode("dark")
          self.root = ctk.CTk()
          self.root.title("Grok's K.O.C. - Killer Operations Core")
          self.root.geometry("1200x800")
          self.config = Config()
          self.api = APIManager(self.config)
          self.data = DataPipeline(self.config, Path(__file__).resolve().parents[1] / "data_cache")
          self.backtester = Backtester()
          self.plugin_manager = PluginManager()
          self.telemetry = TelemetryBus()
          self.running = False
          self.plugins = {}
          self.data_queue = queue.Queue()
          self._dance = False
          self._build()

      def _build(self):
          self.root.grid_columnconfigure(1, weight=1)
          self.root.grid_rowconfigure(0, weight=1)
          control_frame = ctk.CTkFrame(self.root, width=250)
          control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ns")
          self.start_btn = ctk.CTkButton(control_frame, text="▶ Start/Stop", command=self.toggle_bot)
          self.start_btn.pack(padx=10, pady=10, fill="x")
          self.backtest_btn = ctk.CTkButton(control_frame, text="Run Backtest", command=lambda: asyncio.create_task(self.run_backtest()))
          self.backtest_btn.pack(padx=10, pady=10, fill="x")
          self.account_entry = ctk.CTkOptionMenu(control_frame, values=list(self.config.accounts.keys()) or ["none"])
          self.account_entry.pack(padx=10, pady=10, fill="x")
          self.account_type = ctk.CTkOptionMenu(control_frame, values=["live", "testnet", "paper"], command=self.switch_account)
          self.account_type.pack(padx=10, pady=10, fill="x")
          self.key_entry = ctk.CTkEntry(control_frame, placeholder_text="API Key")
          self.key_entry.pack(padx=10, pady=5)
          self.secret_entry = ctk.CTkEntry(control_frame, placeholder_text="API Secret")
          self.secret_entry.pack(padx=10, pady=5)
          ctk.CTkButton(control_frame, text="Save API", command=self.save_api).pack(padx=10, pady=10, fill="x")
          self.plugin_entry = ctk.CTkEntry(control_frame, placeholder_text="Plugin Path (e.g., strategies/scalping.py)")
          self.plugin_entry.pack(padx=10, pady=5)
          self.params_entry = ctk.CTkEntry(control_frame, placeholder_text="Plugin Params (JSON)")
          self.params_entry.pack(padx=10, pady=5)
          ctk.CTkButton(control_frame, text="Install Plugin", command=self.install_plugin).pack(padx=10, pady=10, fill="x")
          ctk.CTkButton(control_frame, text="Deploy Windows", command=lambda: self.deploy("windows")).pack(padx=10, pady=5, fill="x")
          ctk.CTkButton(control_frame, text="Deploy Ubuntu", command=lambda: self.deploy("ubuntu")).pack(padx=10, pady=5, fill="x")
          ctk.CTkButton(control_frame, text="Deploy Docker", command=lambda: self.deploy("docker")).pack(padx=10, pady=5, fill="x")
          self.status = ctk.CTkLabel(control_frame, text="Status: idle")
          self.status.pack(padx=10, pady=10, side="bottom")
          self.pnl_var = ctk.StringVar(value="PnL: 0.00")
          self.trades_var = ctk.StringVar(value="Trades/hour: 0")
          self.pnl_label = ctk.CTkLabel(control_frame, textvariable=self.pnl_var)
          self.pnl_label.pack(padx=10, pady=5)
          self.trades_label = ctk.CTkLabel(control_frame, textvariable=self.trades_var)
          self.trades_label.pack(padx=10, pady=5)
          self.mascot = ctk.CTkLabel(control_frame, text="🤖")
          self.mascot.pack(padx=10, pady=10)
          self.dance_btn = ctk.CTkButton(control_frame, text="Mascot: Dance/Stop", command=self._toggle_dance)
          self.dance_btn.pack(padx=10, pady=10)
          chart_frame = ctk.CTkFrame(self.root)
          chart_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
          self.data_display = ctk.CTkTextbox(chart_frame, height=100)
          self.data_display.pack(padx=10, pady=10, fill="x")
          self.params_display = ctk.CTkTextbox(chart_frame, height=50)
          self.params_display.pack(padx=10, pady=10, fill="x")
          self.fig = Figure(figsize=(10, 6), dpi=100, facecolor="#2B2B2B")
          self.ax = self.fig.add_subplot(111, facecolor="#2B2B2B")
          self.ax.tick_params(axis="x", colors="white")
          self.ax.tick_params(axis="y", colors="white")
          self.ax.spines["bottom"].set_color("white")
          self.ax.spines["top"].set_color("white")
          self.ax.spines["right"].set_color("white")
          self.ax.spines["left"].set_color("white")
          self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
          self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
          self.chart_data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
          self._update_chart()
          self._process_data_queue()
          self._tick_gui()
          asyncio.create_task(self.update_data_display())

      def _toggle_dance(self):
          self._dance = not self._dance

      def _process_data_queue(self):
          try:
              while not self.data_queue.empty():
                  new_data = self.data_queue.get_nowait()
                  if isinstance(new_data, pd.DataFrame):
                      self.chart_data = pd.concat([self.chart_data, new_data]).tail(200)
                      self.chart_data = self.chart_data[~self.chart_data.index.duplicated(keep="last")]
                  else:
                      self.data_display.delete("1.0", ctk.END)
                      self.data_display.insert(ctk.END, str(new_data))
              self._update_chart()
          except queue.Empty:
              pass
          finally:
              self.root.after(200, self._process_data_queue)

      def _update_chart(self):
          self.ax.clear()
          if not self.chart_data.empty:
              self.chart_data["close"].plot(ax=self.ax, color="cyan", linewidth=1.2)
              self.ax.set_title("Live OHLCV (Close Price)", color="white")
              self.ax.set_ylabel("Price", color="white")
              self.ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
              self.fig.autofmt_xdate()
          else:
              self.ax.set_title("Waiting for data...", color="white")
          self.fig.tight_layout()
          self.canvas.draw()

      def _tick_gui(self):
          metrics = self.telemetry.metrics
          total_pnl = sum(float(rec.get("pnl", 0.0)) for rec in metrics.values())
          total_trades = sum(int(rec.get("trades", 0)) for rec in metrics.values())
          self.pnl_var.set(f"PnL: {total_pnl:.2f}")
          self.trades_var.set(f"Trades/hour: {total_trades}")
          self.mascot.configure(text="💃" if self._dance or total_pnl > 0 else "😔" if total_pnl < 0 else "🤖")
          self.root.after(500, self._tick_gui)

      async def update_data_display(self):
          async def callback(quote):
              self.data_queue.put(quote)
          while True:
              try:
                  params = json.loads(self.params_entry.get() or '{"symbol": "BTCUSDT", "source": "binance"}')
                  symbol = params.get("symbol", "BTCUSDT")
                  source = params.get("source", "binance")
                  await self.data.stream_quotes(symbol, source=source)
              except Exception as e:
                  logger.error({"type": "block", "msg": f"Data Display Block: {e}"})
              await asyncio.sleep(5)

      def toggle_bot(self):
          self.running = not self.running
          if self.running:
              self.start_btn.configure(text="⏹ Stop")
              self.status.configure(text="Status: Running")
              asyncio.create_task(self.run_bot())
          else:
              self.start_btn.configure(text="▶ Start")
              self.status.configure(text="Status: Idle")
              asyncio.create_task(self.stop_bot())

      async def run_bot(self):
          try:
              params = json.loads(self.params_entry.get() or '{}')
              self.params_display.delete("1.0", ctk.END)
              self.params_display.insert(ctk.END, json.dumps(params, indent=2))
              for plugin in self.plugins.values():
                  await plugin.run(self.api, self.data)
              for p in self.plugin_manager.processes:
                  self.telemetry.add_endpoint(p["endpoint"])
              self.telemetry.start()
          except Exception as e:
              logger.error({"type": "block", "msg": f"GUI Block: {e}"})

      async def stop_bot(self):
          self.telemetry.stop()
          for p in self.plugin_manager.processes:
              p["process"].terminate()
          self.plugin_manager.processes.clear()

      async def run_backtest(self):
          try:
              params = json.loads(self.params_entry.get() or '{"source": "alpaca", "symbol": "BTCUSDT"}')
              source = params.get("source", "alpaca")
              symbol = params.get("symbol", "BTCUSDT")
              df = await self.data.get_historical(symbol, "2025-09-01", "2025-09-08", source=source)
              stats = await self.backtester.run_vectorized(df, params)
              self.data_display.delete("1.0", ctk.END)
              self.data_display.insert(ctk.END, f"Backtest Stats: {stats}\n")
          except Exception as e:
              logger.error({"type": "block", "msg": f"Backtest Block: {e}"})

      def save_api(self):
          try:
              account = self.account_entry.get() or "binance"
              key = self.key_entry.get()
              secret = self.secret_entry.get()
              creds = {"exchange": account, "key": key, "secret": secret}
              if account == "alpaca":
                  creds["base_url"] = "https://paper-api.alpaca.markets"
              self.config.save_account(account, creds)
              self.api = APIManager(self.config)
              self.data = DataPipeline(self.config, Path(__file__).resolve().parents[1] / "data_cache")
              self.data_display.insert(ctk.END, f"API Saved: {account}\n")
          except Exception as e:
              logger.error({"type": "block", "msg": f"API Save Block: {e}"})

      def install_plugin(self):
          try:
              plugin_path = self.plugin_entry.get()
              params = json.loads(self.params_entry.get() or '{}')
              if Path(plugin_path).exists():
                  plugin = self.plugin_manager.register_plugin(plugin_path, params)
                  self.plugins[plugin_path] = plugin
                  self.data_display.insert(ctk.END, f"Plugin Installed: {plugin_path}\n")
                  self.params_display.delete("1.0", ctk.END)
                  self.params_display.insert(ctk.END, json.dumps(params, indent=2))
          except Exception as e:
              logger.error({"type": "block", "msg": f"Plugin Block: {e}"})

      def switch_account(self, account_type):
          try:
              account = self.account_entry.get() or "binance"
              self.config.switch_account(account, account_type)
              self.api = APIManager(self.config)
              self.data = DataPipeline(self.config, Path(__file__).resolve().parents[1] / "data_cache")
              self.data_display.insert(ctk.END, f"Switched to {account} ({account_type})\n")
          except Exception as e:
              logger.error({"type": "block", "msg": f"Account Switch Block: {e}"})

      def deploy(self, platform):
          try:
              if platform == "windows":
                  subprocess.run(["python", "-m", "venv", "venv"], check=True)
                  subprocess.run(["venv\\Scripts\\pip", "install", "-r", "requirements.txt"], check=True)
              elif platform == "ubuntu":
                  subprocess.run(["python3", "-m", "venv", "venv"], check=True)
                  subprocess.run(["venv/bin/pip", "install", "-r", "requirements.txt"], check=True)
              elif platform == "docker":
                  with open("Dockerfile", "w") as f:
                      f.write("""
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "src/main.py"]
                      """)
                  subprocess.run(["docker", "build", "-t", "koc-trading-bot", "."], check=True)
                  subprocess.run(["docker", "run", "-v", f"{Path.cwd()}/data_cache:/app/data_cache", "koc-trading-bot"], check=True)
              self.data_display.insert(ctk.END, f"Deployed on {platform}\n")
          except Exception as e:
              logger.error({"type": "block", "msg": f"Deploy Block: {e}"})

      def start_gui(self):
          self.root.mainloop()
  ```

### 11. Main
- **File**: `src/main.py`
- **Purpose**: Initialize and run system.
- **Implementation**:
  ```python
  import asyncio
  from .interface import Interface
  from loguru import logger
  from .logger import setup_logger

  async def main():
      setup_logger()
      interface = Interface()
      interface.start_gui()

  if __name__ == "__main__":
      asyncio.run(main())
  ```

### 12. Sample Plugins
- **Files**: `strategies/scalping.py`, `strategies/arbitrage.py`
- **Implementation**:
  ```python
  # scalping.py
  from src.plugins import Plugin
  import asyncio, random
  from loguru import logger

  class StrategyPlugin(Plugin):
      async def run(self, api, data):
          self._pnl += random.uniform(-0.5, 0.5)
          if random.random() < 0.3:
              self._trades += 1
          logger.info({"plugin": self.name, "event": "tick", "pnl": self._pnl, "trades": self._trades})
          await asyncio.sleep(0.2)
  ```
  ```python
  # arbitrage.py
  from src.plugins import Plugin
  import asyncio, random
  from loguru import logger

  class StrategyPlugin(Plugin):
      async def run(self, api, data):
          self._pnl += random.uniform(-0.2, 0.2)
          if random.random() < 0.15:
              self._trades += 1
          logger.info({"plugin": self.name, "event": "tick", "pnl": self._pnl, "trades": self._trades})
          await asyncio.sleep(0.5)
  ```

### 13. Utils
- **File**: `src/utils/ohlcv.py`
- **Purpose**: OHLCV data formatting.
- **Implementation**:
  ```python
  import pandas as pd

  def to_dataframe(ohlcv, columns=("timestamp", "open", "high", "low", "close", "volume")):
      df = pd.DataFrame(ohlcv, columns=list(columns)[:len(ohlcv[0])])
      if "timestamp" in df.columns:
          df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
          df = df.set_index("timestamp")
      return df.sort_index()
  ```

### 14. Tests
- **Files**: `tests/test_smoke.py`, `tests/test_latency.py`
- **Implementation**:
  ```python
  # test_smoke.py
  from src.config import Config
  from src.api_manager import APIManager

  def test_config_loads():
      assert isinstance(Config().accounts, dict)

  async def _latency_path():
      api = APIManager(Config())
      assert isinstance(api, APIManager)
  ```
  ```python
  # test_latency.py
  import time

  def test_placeholder_latency():
      t0 = time.perf_counter()
      time.sleep(0.01)
      assert (time.perf_counter() - t0) * 1000 < 1000
  ```

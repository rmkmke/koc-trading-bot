import customtkinter as ctk
from loguru import logger
import queue
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mticker


class Interface:
    def __init__(self, on_start, on_stop, on_switch_account, data_queue, initial_accounts, metrics_provider=None, on_backtest=None):
        ctk.set_appearance_mode("dark")
        self.app = ctk.CTk()
        self.app.title("Grok's K.O.C.")
        self.app.geometry("1200x800")
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_switch_account = on_switch_account
        self.on_backtest = on_backtest
        self.data_queue = data_queue
        self.initial_accounts = initial_accounts
        self.metrics_provider = metrics_provider
        self.chart_data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        self.backtest_equity = None
        self.bt_stats_var = ctk.StringVar(value="Backtest: n/a")
        self._dance = False
        self._build()
        self._process_data_queue()
        self._tick_gui()

    def _build(self):
        self.app.grid_columnconfigure(1, weight=1)
        self.app.grid_rowconfigure(0, weight=1)
        control_frame = ctk.CTkFrame(self.app, width=250)
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ns")
        self.start_btn = ctk.CTkButton(control_frame, text="▶ Start Streaming", command=self.on_start)
        self.start_btn.pack(padx=10, pady=10, fill="x")
        self.stop_btn = ctk.CTkButton(control_frame, text="⏹ Stop Streaming", command=self.on_stop, state="disabled")
        self.stop_btn.pack(padx=10, pady=10, fill="x")
        self.account_menu = ctk.CTkOptionMenu(control_frame, values=self.initial_accounts)
        self.account_menu.pack(padx=10, pady=20, fill="x")
        self.account_menu.set(self.initial_accounts[0] if self.initial_accounts else "none")
        self.status = ctk.CTkLabel(control_frame, text="Status: idle")
        self.status.pack(padx=10, pady=10, side="bottom")
        # Backtest controls
        ctk.CTkLabel(control_frame, text="Backtest").pack(padx=10, pady=(10, 0))
        self.bt_symbol = ctk.CTkEntry(control_frame, placeholder_text="Symbol (e.g., BTC/USDT)")
        self.bt_symbol.insert(0, "BTC/USDT")
        self.bt_symbol.pack(padx=10, pady=5, fill="x")
        self.bt_timeframe = ctk.CTkOptionMenu(control_frame, values=["1m", "5m", "15m", "1h"])
        self.bt_timeframe.set("1m")
        self.bt_timeframe.pack(padx=10, pady=5, fill="x")
        self.bt_limit = ctk.CTkEntry(control_frame, placeholder_text="Limit (e.g., 500)")
        self.bt_limit.insert(0, "500")
        self.bt_limit.pack(padx=10, pady=5, fill="x")
        self.bt_strategy = ctk.CTkOptionMenu(control_frame, values=["rsi", "sma", "momentum"])
        self.bt_strategy.set("rsi")
        self.bt_strategy.pack(padx=10, pady=5, fill="x")
        self.bt_window = ctk.CTkEntry(control_frame, placeholder_text="Window (e.g., 14)")
        self.bt_window.insert(0, "14")
        self.bt_window.pack(padx=10, pady=5, fill="x")
        self.bt_button = ctk.CTkButton(control_frame, text="Run Backtest", command=self._run_backtest_clicked)
        self.bt_button.pack(padx=10, pady=10, fill="x")
        self.bt_stats = ctk.CTkLabel(control_frame, textvariable=self.bt_stats_var)
        self.bt_stats.pack(padx=10, pady=5, fill="x")
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
        chart_frame = ctk.CTkFrame(self.app)
        chart_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
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
        self._update_chart()

    def _process_data_queue(self):
        try:
            while not self.data_queue.empty():
                payload = self.data_queue.get_nowait()
                if isinstance(payload, pd.DataFrame):
                    new_data_df = payload
                    self.chart_data = pd.concat([self.chart_data, new_data_df]).tail(200)
                    self.chart_data = self.chart_data[~self.chart_data.index.duplicated(keep="last")]
                elif isinstance(payload, dict) and payload.get("backtest"):
                    result = payload["backtest"]
                    self.backtest_equity = result.get("equity")
                    sharpe = result.get("sharpe", 0.0)
                    ret = result.get("total_return", 0.0)
                    trades = result.get("trades", 0)
                    self.bt_stats_var.set(f"Backtest: Sharpe {sharpe:.2f} | Return {ret:.2%} | Trades {trades}")
            self._update_chart()
        except queue.Empty:
            pass
        finally:
            self.app.after(200, self._process_data_queue)

    def _update_chart(self):
        self.ax.clear()
        if self.backtest_equity is not None and not getattr(self.backtest_equity, "empty", False):
            self.backtest_equity.plot(ax=self.ax, color="yellow", linewidth=1.2)
            self.ax.set_title("Backtest Equity Curve", color="white")
            self.ax.set_ylabel("Equity", color="white")
        elif not self.chart_data.empty:
            self.chart_data["close"].plot(ax=self.ax, color="cyan", linewidth=1.2)
            self.ax.set_title("Live OHLCV (Close Price)", color="white")
            self.ax.set_ylabel("Price", color="white")
            self.ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
            self.fig.autofmt_xdate()
        else:
            self.ax.set_title("Waiting for data...", color="white")
        self.fig.tight_layout()
        self.canvas.draw()

    def _toggle_dance(self):
        self._dance = not self._dance

    def _tick_gui(self):
        if self.metrics_provider:
            metrics = self.metrics_provider()
            total_pnl = sum(float(rec.get("pnl", 0.0)) for rec in metrics.values())
            total_trades = sum(int(rec.get("trades", 0)) for rec in metrics.values())
            self.pnl_var.set(f"PnL: {total_pnl:.2f}")
            self.trades_var.set(f"Trades/hour: {total_trades}")
            self.mascot.configure(text="💃" if self._dance or total_pnl > 0 else "😔" if total_pnl < 0 else "🤖")
        self.app.after(500, self._tick_gui)

    def set_status(self, text):
        self.status.configure(text=text)

    def _run_backtest_clicked(self):
        if not self.on_backtest:
            logger.warning("Backtest callback not configured")
            return
        try:
            params = {
                "exchange": self.account_menu.get() or "binance",
                "symbol": self.bt_symbol.get() or "BTC/USDT",
                "timeframe": self.bt_timeframe.get() or "1m",
                "limit": int(self.bt_limit.get() or 500),
                "strategy": self.bt_strategy.get() or "rsi",
                "window": int(self.bt_window.get() or 14),
            }
            self.on_backtest(params)
            self.set_status("Status: Running backtest...")
        except Exception as e:
            logger.error(f"Backtest param error: {e}")

    def run(self):
        self.app.mainloop()

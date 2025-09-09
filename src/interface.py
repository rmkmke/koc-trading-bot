import customtkinter as ctk
from loguru import logger
import queue
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mticker


class Interface:
    def __init__(self, on_start, on_stop, on_switch_account, data_queue, initial_accounts, metrics_provider=None):
        ctk.set_appearance_mode("dark")
        self.app = ctk.CTk()
        self.app.title("Grok's K.O.C.")
        self.app.geometry("1200x800")
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_switch_account = on_switch_account
        self.data_queue = data_queue
        self.initial_accounts = initial_accounts
        self.metrics_provider = metrics_provider
        self.chart_data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
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
                new_data_df = self.data_queue.get_nowait()
                self.chart_data = pd.concat([self.chart_data, new_data_df]).tail(200)
                self.chart_data = self.chart_data[~self.chart_data.index.duplicated(keep="last")]
            self._update_chart()
        except queue.Empty:
            pass
        finally:
            self.app.after(200, self._process_data_queue)

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

    def run(self):
        self.app.mainloop()


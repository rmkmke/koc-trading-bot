import asyncio, sys, threading, queue
from pathlib import Path
from loguru import logger
from src.logger import setup_logger
from src.config import load_config, switch_account
from src.api_manager import APIManager
from src.data_pipeline import DataPipeline
from src.plugins import load_plugins
from src.telemetry import TelemetryBus
from apscheduler.schedulers.asyncio import AsyncIOScheduler


def _make_gui(start_cb, stop_cb, switch_cb, data_q, accounts, metrics_provider):
    from src.interface import Interface

    return Interface(start_cb, stop_cb, switch_cb, data_q, accounts, metrics_provider)


class App:
    def __init__(self):
        setup_logger()
        self.cfg = load_config()
        self.api = APIManager(self.cfg)
        self.dp = DataPipeline(Path(__file__).resolve().parents[1] / "data_cache")
        self.scheduler = AsyncIOScheduler()
        self.telemetry = TelemetryBus()
        self.gui = None
        self.plugins = []
        self.running = False
        self.data_queue = queue.Queue()
        self.stream_thread = None
        self.stop_stream_event = threading.Event()

    async def _stream_target(self, exchange, symbol, timeframe):
        try:
            await self.dp.stream_ohlcv(exchange, symbol, timeframe, self.data_queue)
        except Exception as e:
            logger.error(f"Stream target error: {e}")

    async def start(self):
        if self.running:
            logger.warning("Stream already running")
            return
        self.running = True
        self.stop_stream_event.clear()
        if self.gui:
            self.gui.set_status("Status: Starting...")
            self.gui.start_btn.configure(state="disabled")
            self.gui.stop_btn.configure(state="normal")
        exchange = self.gui.account_menu.get() if self.gui else "binance"
        symbol = "BTC/USDT"
        timeframe = "1m"
        logger.info(f"Starting stream for {symbol} on {exchange}")
        self.plugins = load_plugins(Path(__file__).resolve().parents[1] / "strategies")
        for p in self.plugins:
            self.telemetry.add_endpoint(p["endpoint"])
        self.telemetry.start()
        self.scheduler.start()

        def thread_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._stream_target(exchange, symbol, timeframe))
            logger.info("Stream thread finished")

        self.stream_thread = threading.Thread(target=thread_loop, daemon=True)
        self.stream_thread.start()
        if self.gui:
            self.gui.set_status(f"Status: Streaming {symbol}")

    async def stop(self):
        if not self.running:
            logger.warning("Stream not running")
            return
        logger.info("Stopping stream")
        self.stop_stream_event.set()
        await self.dp.close()
        self.running = False
        self.telemetry.stop()
        self.scheduler.shutdown(wait=False)
        if self.gui:
            self.gui.set_status("Status: Idle")
            self.gui.start_btn.configure(state="normal")
            self.gui.stop_btn.configure(state="disabled")

    def toggle_account(self, new_mode):
        switch_account(self.cfg, self.gui.account_menu.get(), new_mode)
        logger.info({"event": "account_switched", "mode": new_mode})

    def metrics_provider(self):
        return self.telemetry.metrics

    async def run_asyncio_forever(self):
        while True:
            await asyncio.sleep(0.5)


def main():
    app = App()

    async def start_coro():
        await app.start()

    async def stop_coro():
        await app.stop()

    def on_start():
        asyncio.ensure_future(start_coro())

    def on_stop():
        asyncio.ensure_future(stop_coro())

    def on_switch(mode):
        app.toggle_account(mode)

    try:
        accounts = list(app.cfg.keys()) if app.cfg else []
        app.gui = _make_gui(on_start, on_stop, on_switch, app.data_queue, accounts, app.metrics_provider)
    except Exception as e:
        logger.warning({"event": "gui_init_failed", "err": str(e)})
        app.gui = None
    loop = asyncio.get_event_loop()
    if app.gui:
        loop.create_task(app.run_asyncio_forever())
        app.gui.run()
    else:
        loop.run_until_complete(app.run_asyncio_forever())


if __name__ == "__main__":
    if sys.platform != "win32":
        try:
            import uvloop

            uvloop.install()
        except Exception:
            pass
    main()


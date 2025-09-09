import asyncio, time
from loguru import logger
import ccxt.async_support as ccxt
from src.resilience import transient_retry, exchange_circuit

class APIManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self.clients = {}
        self.rate_limits = {}

    async def get_client(self, name):
        if name not in self.clients:
            section = self.cfg.get(name, {})
            exchange_id = section.get("exchange", name)
            client = getattr(ccxt, exchange_id)({
                "apiKey": section.get("apiKey"),
                "secret": section.get("secret"),
                "enableRateLimit": True,
                **section.get("options", {}),
            })
            if section.get("account") == "testnet":
                try:
                    client.set_sandbox_mode(True)
                except Exception:
                    pass
            self.clients[name] = client
            self.rate_limits[name] = {"last_weight": 0, "last_ts": time.time()}
        return self.clients[name]

    @exchange_circuit
    @transient_retry()
    async def execute_order(self, name, symbol, side, type_, amount, price=None):
        t0 = time.perf_counter()
        client = await self.get_client(name)
        order = await client.create_order(symbol, type_, side, amount, price)
        latency_ms = (time.perf_counter() - t0) * 1000
        if latency_ms > 500:
            logger.warning({"event": "order_latency_high", "exchange": name, "latency_ms": latency_ms})
        logger.info({"event": "order_executed", "exchange": name, "symbol": symbol, "latency_ms": latency_ms})
        return {"order": order, "latency_ms": latency_ms}

    async def track_rate_limits(self, name, headers=None):
        # Placeholder for venue-specific rate limit parsing
        pass


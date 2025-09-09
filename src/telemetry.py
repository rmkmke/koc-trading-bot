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
                        if k in ("plugin", "event"):
                            continue
                        if isinstance(v, (int, float)):
                            rec[k] = v
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


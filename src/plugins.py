import importlib.util, inspect, multiprocessing as mp, zmq, time
from pathlib import Path
from loguru import logger


class Plugin:
    def run(self, api, data):
        raise NotImplementedError

    def __init__(self):
        self._pnl = 0.0
        self._trades = 0


def _child_worker(module_path, class_name, zmq_endpoint):
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.PUB)
    sock.bind(zmq_endpoint)
    try:
        spec = importlib.util.spec_from_file_location("plugin_mod", module_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        plugin = getattr(mod, class_name)()
        start_time = time.time()
        while True:
            try:
                plugin.run(api=None, data={})
                sock.send_json({
                    "plugin": class_name,
                    "ts": time.time(),
                    "event": "tick",
                    "pnl": getattr(plugin, "_pnl", 0.0),
                    "trades": getattr(plugin, "_trades", 0),
                })
                if time.time() - start_time > 10:
                    logger.warning({"event": "plugin_risk", "issue": "high_cpu", "plugin": class_name})
                time.sleep(1)
            except Exception as e:
                logger.warning({"event": "plugin_error", "plugin": class_name, "error": str(e)})
                time.sleep(2)
    finally:
        try:
            sock.close()
        except Exception:
            pass


def load_plugins(strategies_dir: Path):
    procs = []
    strategies_dir = Path(strategies_dir)
    for py in strategies_dir.glob("*.py"):
        if py.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location("tmp_mod", py)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        cls = next(
            (
                obj
                for name, obj in inspect.getmembers(mod, inspect.isclass)
                if issubclass(obj, Plugin) and obj is not Plugin
            ),
            None,
        )
        if cls:
            endpoint = f"tcp://127.0.0.1:{_free_port()}"
            p = mp.Process(target=_child_worker, args=(str(py), cls.__name__, endpoint), daemon=True)
            p.start()
            procs.append({"process": p, "endpoint": endpoint, "file": str(py), "class": cls.__name__})
    return procs


def _free_port():
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


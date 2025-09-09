from src.plugins import Plugin
import random, time
from loguru import logger


class Scalping(Plugin):
    def __init__(self):
        super().__init__()
        self._pnl = 0.0
        self._trades = 0

    def run(self, api, data):
        self._pnl += random.uniform(-0.5, 0.5)
        if random.random() < 0.3:
            self._trades += 1
        logger.info({"plugin": "Scalping", "event": "tick"})
        time.sleep(0.2)


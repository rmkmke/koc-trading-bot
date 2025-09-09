from src.plugins import Plugin
import random, time
from loguru import logger


class SimpleArbitrage(Plugin):
    def __init__(self):
        super().__init__()
        self._pnl = 0.0
        self._trades = 0

    def run(self, api, data):
        self._pnl += random.uniform(-0.2, 0.2)
        if random.random() < 0.15:
            self._trades += 1
        logger.info({"plugin": "SimpleArbitrage", "event": "tick"})
        time.sleep(0.5)


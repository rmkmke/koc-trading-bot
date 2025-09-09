from loguru import logger
from pathlib import Path
import sys, json

LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "koc.json"

def setup_logger(level="INFO"):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stdout, level=level, serialize=False)
    logger.add(LOG_PATH, level="DEBUG", serialize=True, rotation="10 MB", retention=10)
    logger.debug(json.dumps({"event": "logger_initialized", "path": str(LOG_PATH)}))
    return logger


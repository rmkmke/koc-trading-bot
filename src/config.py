import os, yaml, keyring
from pathlib import Path
from loguru import logger

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "accounts.yaml"

def load_config():
    cfg = yaml.safe_load(CONFIG_PATH.open("r", encoding="utf-8")) if CONFIG_PATH.exists() else {}
    if os.getenv("KOC_DOCKER") == "1":
        for name in cfg:
            for key in ["apiKey", "secret"]:
                path = Path(f"/run/secrets/{name}_{key}")
                if path.exists():
                    cfg[name][key] = path.read_text().strip()
    else:
        for name in cfg:
            for key in ["apiKey", "secret"]:
                kr_val = keyring.get_password("koc", f"koc:{name}:{key}")
                if kr_val:
                    cfg[name][key] = kr_val
    return cfg

def switch_account(cfg, exchange_name, account_type):
    cfg.setdefault(exchange_name, {})
    cfg[exchange_name]["account"] = account_type
    if exchange_name == "alpaca":
        cfg[exchange_name]["base_url"] = (
            "https://paper-api.alpaca.markets" if account_type == "paper" else "https://api.alpaca.markets"
        )
    elif exchange_name == "binance":
        cfg[exchange_name]["enableRateLimit"] = True
        cfg[exchange_name]["set_sandbox_mode"] = (account_type == "testnet")
    logger.info({"event": "account_switched", "exchange": exchange_name, "type": account_type})
    return cfg


from src.config import load_config
from src.api_manager import APIManager


def test_config_loads():
    assert isinstance(load_config(), dict)


async def _latency_path():
    api = APIManager({})
    assert isinstance(api, APIManager)


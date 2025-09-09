from tenacity import retry, stop_after_attempt, wait_random_exponential
import pybreaker
from loguru import logger

exchange_circuit = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30, name="exchange_circuit")

def transient_retry(**kw):
    def before_sleep(retry_state):
        logger.warning({"event": "retry_attempt", "attempt": retry_state.attempt_number})
    return retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(multiplier=0.2, max=2),
        before_sleep=before_sleep,
        **kw,
    )


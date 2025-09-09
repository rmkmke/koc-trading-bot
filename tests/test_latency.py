import time


def test_placeholder_latency():
    t0 = time.perf_counter()
    time.sleep(0.01)
    assert (time.perf_counter() - t0) * 1000 < 1000


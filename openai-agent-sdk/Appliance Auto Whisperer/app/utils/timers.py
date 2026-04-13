import time
from contextlib import contextmanager
from collections.abc import Iterator


@contextmanager
def timer() -> Iterator[list[float]]:
    t0 = time.perf_counter()
    out: list[float] = []
    try:
        yield out
    finally:
        out.append(time.perf_counter() - t0)

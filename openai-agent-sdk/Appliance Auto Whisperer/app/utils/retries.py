from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def async_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    delay_s: float = 0.5,
) -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if i < attempts - 1:
                await asyncio.sleep(delay_s * (2**i))
    assert last is not None
    raise last

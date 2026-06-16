"""
Generic async retry wrapper with exponential back-off.
"""

import asyncio
import logging
from typing import Callable, TypeVar, Any

T = TypeVar("T")

log = logging.getLogger(__name__)


async def with_retry(
    fn: Callable[..., Any],
    *args,
    max_retries: int = 2,
    backoff: float = 5.0,
    label: str = "",
    **kwargs,
) -> Any:
    """
    Call *fn* up to (1 + max_retries) times.
    On failure, wait `backoff * attempt` seconds before retrying.
    Returns the result of *fn* on success.
    Raises the last exception if all retries are exhausted.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait = backoff * (attempt + 1)
                log.warning(
                    "%s failed (attempt %d/%d): %s — retrying in %.0fs",
                    label or fn.__name__,
                    attempt + 1,
                    max_retries + 1,
                    str(e)[:120],
                    wait,
                )
                await asyncio.sleep(wait)
            else:
                log.error(
                    "%s failed after %d attempts: %s",
                    label or fn.__name__,
                    max_retries + 1,
                    str(e)[:200],
                )
    raise last_error  # type: ignore[misc]

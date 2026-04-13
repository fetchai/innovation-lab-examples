"""Distributed tracing hook — wire to OpenTelemetry as needed."""

from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[None]:
    _ = (name, attrs)
    yield None

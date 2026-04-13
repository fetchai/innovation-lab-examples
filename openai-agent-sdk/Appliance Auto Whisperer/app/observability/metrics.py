"""Counters/histograms hook — wire to Prometheus/OpenTelemetry as needed."""

_counters: dict[str, int] = {}


def inc(name: str, n: int = 1) -> None:
    _counters[name] = _counters.get(name, 0) + n


def snapshot() -> dict[str, int]:
    return dict(_counters)

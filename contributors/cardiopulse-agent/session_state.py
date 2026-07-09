"""
Shared in-memory state for incoming BPM readings.

Both the REST endpoint (which receives readings from bridge_agent.py) and the
chat handler (which reads them during a test) live in the same Python process,
so a simple module-level buffer with a lock is enough.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

# Last ~15 minutes of readings — plenty for a 3-minute test plus margin.
_BPM_BUFFER: deque[tuple[float, int]] = deque(maxlen=900)
_RR_BUFFER: deque[tuple[float, float]] = deque(maxlen=3000)
_LAST_TS: float = 0.0
_LOCK = Lock()


def receive_bpm(bpm: int, rr_intervals: list[float], ts: float) -> None:
    """Record one reading from the BLE bridge."""
    global _LAST_TS
    with _LOCK:
        _BPM_BUFFER.append((ts, bpm))
        for rr in rr_intervals:
            _RR_BUFFER.append((ts, rr))
        _LAST_TS = ts


def bpm_in_window(start_ts: float, end_ts: float) -> list[int]:
    """Return just the BPM values recorded between two timestamps."""
    with _LOCK:
        return [bpm for ts, bpm in _BPM_BUFFER if start_ts <= ts <= end_ts]


def bpm_series_in_window(start_ts: float, end_ts: float) -> list[tuple[float, int]]:
    """Return (timestamp, BPM) tuples between two timestamps — for charting."""
    with _LOCK:
        return [(ts, bpm) for ts, bpm in _BPM_BUFFER if start_ts <= ts <= end_ts]


def rr_in_window(start_ts: float, end_ts: float) -> list[float]:
    """Return RR intervals recorded between two timestamps."""
    with _LOCK:
        return [rr for ts, rr in _RR_BUFFER if start_ts <= ts <= end_ts]


def is_streaming(max_age_sec: float = 5.0) -> bool:
    """True if a reading arrived in the last `max_age_sec` seconds."""
    with _LOCK:
        return (time.time() - _LAST_TS) < max_age_sec


def latest_bpm() -> int | None:
    """Most recent BPM reading, or None if none have arrived yet."""
    with _LOCK:
        if not _BPM_BUFFER:
            return None
        return _BPM_BUFFER[-1][1]

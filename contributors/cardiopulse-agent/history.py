"""
Persistent test history.

Saves every completed cardio fitness test to a JSON file so subsequent runs
can compare against prior results — "your Cardio Age dropped from 30 to 27 in
the last two weeks" beats a single isolated number every time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from scoring import TestResult

_DATA_DIR = Path(__file__).parent / "data"
_HISTORY_FILE = _DATA_DIR / "test_history.json"
_LOCK = Lock()


@dataclass
class TestRecord:
    """One stored test result, with a timestamp.

    `sender` is the chat counterpart's agent address — it scopes history to
    one user so trend comparisons never mix different people's tests.
    Records written before this field existed have sender == "".
    """

    timestamp: str  # ISO 8601 UTC
    age: int
    cardio_fitness_age: int
    resting_hr: int
    orthostatic_delta: int
    breathing_variance: float
    rhr_grade: str
    sender: str = ""

    @classmethod
    def from_result(cls, result: TestResult, sender: str = "") -> "TestRecord":
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            age=result.age,
            cardio_fitness_age=result.cardio_fitness_age,
            resting_hr=result.resting_hr,
            orthostatic_delta=result.orthostatic_delta,
            breathing_variance=result.breathing_variance,
            rhr_grade=result.rhr_grade,
            sender=sender,
        )


def _load() -> list[dict]:
    if not _HISTORY_FILE.exists():
        return []
    try:
        return json.loads(_HISTORY_FILE.read_text())
    except Exception:
        return []


def _save(records: list[dict]) -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    _HISTORY_FILE.write_text(json.dumps(records, indent=2))


def append(result: TestResult, sender: str = "") -> None:
    """Persist a new test result to history, scoped to `sender`."""
    with _LOCK:
        records = _load()
        records.append(asdict(TestRecord.from_result(result, sender)))
        _save(records)


def recent(limit: int = 5, sender: str | None = None) -> list[TestRecord]:
    """Return the most recent `limit` records, oldest first.

    If `sender` is given, only that user's records are returned.
    """
    with _LOCK:
        raw = _load()
    if sender is not None:
        raw = [e for e in raw if e.get("sender", "") == sender]
    out: list[TestRecord] = []
    for entry in raw[-limit:]:
        try:
            out.append(TestRecord(**entry))
        except Exception:
            continue
    return out


def previous(sender: str | None = None) -> TestRecord | None:
    """Return the most recent prior test for this sender, or None.

    Call this BEFORE history.append(current_result) so it returns the actual
    previous test rather than the one just recorded.
    """
    with _LOCK:
        raw = _load()
    if sender is not None:
        raw = [e for e in raw if e.get("sender", "") == sender]
    if not raw:
        return None
    try:
        return TestRecord(**raw[-1])
    except Exception:
        return None


def count() -> int:
    with _LOCK:
        return len(_load())


def humanize_delta(days: float) -> str:
    """Friendly time-since label (e.g. '3 days ago', 'just now')."""
    if days < 0.04:  # ~1 hour
        return "less than an hour ago"
    if days < 1:
        hours = round(days * 24)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if days < 7:
        d = round(days)
        return f"{d} day{'s' if d != 1 else ''} ago"
    if days < 30:
        w = round(days / 7)
        return f"{w} week{'s' if w != 1 else ''} ago"
    m = round(days / 30)
    return f"{m} month{'s' if m != 1 else ''} ago"


def time_since(record: TestRecord) -> str:
    """Human-friendly 'X ago' string for a record."""
    try:
        ts = datetime.fromisoformat(record.timestamp)
    except Exception:
        return "an unknown time ago"
    delta_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
    return humanize_delta(delta_seconds / 86400)

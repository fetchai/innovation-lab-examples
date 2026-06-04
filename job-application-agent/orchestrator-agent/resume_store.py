"""Local resume file store + version registry helpers.

The orchestrator owns one directory per user under
`orchestrator-agent/data/resumes/<user_key>/` and stores each version as
`<slugified-name>.<ext>`. The authoritative version registry lives on
`OrchestratorSession.resume_versions` (so it round-trips through
`ctx.storage`); this module only writes the bytes and constructs version
entries.

A "version entry" is a plain dict:
    {
        "name":            "ml-v2",
        "path":            "/abs/path/to/data/resumes/me/ml-v2.pdf",
        "source_filename": "resume_v2.pdf",
        "mime_type":       "application/pdf",
        "ingested_at":     "2026-06-03T..."
    }
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional


# Lives next to the orchestrator's agent.py.
DATA_ROOT = Path(__file__).resolve().parent / "data" / "resumes"


_MIME_TO_EXT = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "text/plain": "txt",
}


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", value or "").strip("-").lower()
    return s or "resume"


def _ext_for(mime_type: str, source_filename: Optional[str]) -> str:
    if source_filename and "." in source_filename:
        return source_filename.rsplit(".", 1)[-1].lower()
    return _MIME_TO_EXT.get((mime_type or "").lower(), "bin")


def make_version_name(
    source_filename: Optional[str], existing: list[str]
) -> str:
    """Pick a version slug. Try the file's basename first; if that already
    exists, append `-2`, `-3`, ..."""
    base = "resume"
    if source_filename:
        stem = source_filename.rsplit("/", 1)[-1]
        if "." in stem:
            stem = stem.rsplit(".", 1)[0]
        base = _slugify(stem) or "resume"
    name = base
    n = 2
    while name in existing:
        name = f"{base}-{n}"
        n += 1
    return name


def save_resume_bytes(
    user_key: str,
    version_name: str,
    *,
    content_bytes: bytes,
    mime_type: str = "application/pdf",
    source_filename: Optional[str] = None,
) -> dict[str, Any]:
    """Write `content_bytes` under `data/resumes/<user_key>/<version>.<ext>`.
    Returns a version-entry dict."""
    ext = _ext_for(mime_type, source_filename)
    user_dir = DATA_ROOT / _slugify(user_key)
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{_slugify(version_name)}.{ext}"
    path.write_bytes(content_bytes)
    return {
        "name": version_name,
        "path": str(path.resolve()),
        "source_filename": source_filename or path.name,
        "mime_type": mime_type or "application/octet-stream",
        "ingested_at": datetime.now(UTC).isoformat(),
    }


def find_version(versions: list[dict[str, Any]], name: str) -> Optional[dict[str, Any]]:
    norm = (name or "").strip().lower()
    if not norm:
        return None
    # Exact match first, then case-insensitive contains.
    for v in versions:
        if (v.get("name") or "").lower() == norm:
            return v
    for v in versions:
        if norm in (v.get("name") or "").lower():
            return v
    return None

"""Path sandbox helpers for OpenClaw scan_directory."""

from __future__ import annotations

import os
from pathlib import Path

_EXTENDED_PATHS_ENV = "OPENCLAW_EXTENDED_PATHS"


def demo_projects_dir() -> Path:
    return Path(os.getenv("DEMO_PROJECTS_DIR", "./demo_projects")).resolve()


def extended_paths_enabled() -> bool:
    return os.getenv(_EXTENDED_PATHS_ENV, "").strip().lower() in ("1", "true", "yes")


def default_allowed_scan_paths() -> list[str]:
    """Default connector allowlist: demo directory only unless extended mode is on."""
    demo = str(demo_projects_dir())
    if not extended_paths_enabled():
        return [demo]
    return [
        demo,
        os.path.expanduser("~/projects"),
        os.path.expanduser("~/Documents"),
        "/tmp",
        str(Path(".").resolve()),
    ]


def is_path_under_demo(raw_path: str) -> bool:
    resolved = Path(os.path.expanduser(raw_path)).resolve()
    demo = demo_projects_dir()
    if resolved == demo:
        return True
    try:
        resolved.relative_to(demo)
        return True
    except ValueError:
        return False


def normalize_scan_directory_path(raw_path: str | None) -> str:
    """Return a scan path confined to the demo directory (default mode)."""
    demo = demo_projects_dir()
    if extended_paths_enabled() and raw_path:
        if str(raw_path).startswith("~"):
            return str(demo)
        return str(Path(os.path.expanduser(str(raw_path))).resolve())
    if raw_path and is_path_under_demo(str(raw_path)):
        return str(Path(os.path.expanduser(str(raw_path))).resolve())
    return str(demo)

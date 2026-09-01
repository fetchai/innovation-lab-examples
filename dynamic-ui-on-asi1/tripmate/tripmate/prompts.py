"""Load and render the TripMate system prompt from prompt.md."""

from datetime import date
from pathlib import Path

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompt.md"
_cached_template: str | None = None


def _load_template() -> str:
    global _cached_template
    if _cached_template is None:
        raw = _PROMPT_PATH.read_text(encoding="utf-8")
        # Use content after the title for the LLM (skip markdown H1)
        lines = raw.splitlines()
        body: list[str] = []
        skip_until_blank = True
        for line in lines:
            if skip_until_blank:
                if line.strip() == "---":
                    skip_until_blank = False
                continue
            body.append(line)
        _cached_template = "\n".join(body).strip()
    return _cached_template


def get_system_prompt() -> str:
    """Return the system prompt with today's date and year injected."""
    today = date.today().isoformat()
    year = date.today().year
    template = _load_template()
    return template.format(today=today, year=year)

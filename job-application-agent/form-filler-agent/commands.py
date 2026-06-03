"""Parse free-text chat commands into a typed Command object.

Recognised shapes (case-insensitive on the verb; field names preserve case):

  apply <url>                  Greenhouse URL detected anywhere in text also triggers this.
  show <name>                  show a single field's full value
  show payload                 dump the prepared submitter payload (after a dry-run)
  show all                     re-print the form panel
  answer <name> <value...>     fill a missing field
  edit    <name> <value...>    change a filled field
  unfill  <name>               clear a filled field
  next                         show the next missing field's prompt
  submit                       run a dry-run submission
  submit live                  actually post to Greenhouse
  cancel                       discard the active session
  help                         print the command list
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


GREENHOUSE_URL_RE = re.compile(
    r"https?://(?:job-)?boards\.greenhouse\.io/[^\s]+",
    re.IGNORECASE,
)


@dataclass
class Command:
    kind: str  # "apply" | "show" | "show_all" | "show_payload" | "answer" |
               # "edit" | "unfill" | "next" | "submit" | "submit_live" |
               # "cancel" | "help" | "unknown" | "noop"
    field_name: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None
    raw: str = ""


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def parse(text: str) -> Command:
    raw = text or ""
    stripped = raw.strip()
    if not stripped:
        return Command(kind="noop", raw=raw)

    # Greenhouse URLs anywhere → treat as `apply`.
    url_match = GREENHOUSE_URL_RE.search(stripped)
    if url_match:
        return Command(kind="apply", url=url_match.group(0), raw=raw)

    lower = stripped.lower()

    if lower in {"help", "?", "/help"}:
        return Command(kind="help", raw=raw)

    if lower in {"cancel", "reset", "abort"}:
        return Command(kind="cancel", raw=raw)

    if lower == "next":
        return Command(kind="next", raw=raw)

    if lower == "submit":
        return Command(kind="submit", raw=raw)

    if lower in {"submit live", "submit real", "submit!", "submit now"}:
        return Command(kind="submit_live", raw=raw)

    if lower in {"show all", "show form", "form", "preview"}:
        return Command(kind="show_all", raw=raw)

    if lower == "show payload":
        return Command(kind="show_payload", raw=raw)

    # show <name>
    m = re.match(r"^show\s+(.+)$", stripped, re.IGNORECASE)
    if m:
        return Command(kind="show", field_name=_strip_quotes(m.group(1)), raw=raw)

    # answer <name> <value...>
    m = re.match(r"^answer\s+(\S+)\s+(.+)$", stripped, re.IGNORECASE | re.DOTALL)
    if m:
        return Command(
            kind="answer",
            field_name=_strip_quotes(m.group(1)),
            value=m.group(2).strip(),
            raw=raw,
        )

    # edit <name> <value...>
    m = re.match(r"^edit\s+(\S+)\s+(.+)$", stripped, re.IGNORECASE | re.DOTALL)
    if m:
        return Command(
            kind="edit",
            field_name=_strip_quotes(m.group(1)),
            value=m.group(2).strip(),
            raw=raw,
        )

    # unfill <name>
    m = re.match(r"^unfill\s+(\S+)$", stripped, re.IGNORECASE)
    if m:
        return Command(kind="unfill", field_name=_strip_quotes(m.group(1)), raw=raw)

    return Command(kind="unknown", raw=raw)

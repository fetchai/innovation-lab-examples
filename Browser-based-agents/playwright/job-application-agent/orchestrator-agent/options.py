"""Fuzzy match a value (e.g. "no", "yes", "us citizen") to the closest
option from a Greenhouse field's option list. Used by:

- The initial post-profile fill pass, to upgrade short LLM/canned answers
  like "No" into the real long option label like "I have never worked
  at Robinhood as a full-time employee or intern."
- The user-edit path, so users can type "yes"/"no"/free text and the
  agent still maps to a valid option.
- The browser filler, to know which dropdown option to click.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Optional


_YES_WORDS = {"yes", "y", "true", "1", "yeah", "yep", "yup", "affirmative"}
_NO_WORDS = {"no", "n", "false", "0", "nope", "nah", "negative"}


def _norm(text: Any) -> str:
    s = str(text or "").lower().strip()
    return re.sub(r"\s+", " ", s)


def _opt_label(o: Any) -> str:
    if isinstance(o, dict):
        return str(o.get("label") or o.get("value") or "")
    return str(o)


def _opt_value(o: Any) -> str:
    if isinstance(o, dict):
        return str(o.get("value") or o.get("label") or "")
    return str(o)


def match_option(
    value: Any, options: list[Any]
) -> Optional[dict[str, str]]:
    """Return {"label", "value"} for the best matching option, or None if
    `options` is empty/no decent match exists. Strategy:

    1. Exact label or value match (case-insensitive).
    2. Yes/No synonyms → option whose label starts with "yes"/"no".
    3. Substring containment either direction.
    4. Fuzzy ratio ≥ 0.55 (only beats other candidates).
    """
    if not options or not isinstance(options, list):
        return None
    v = _norm(value)
    if not v:
        return None

    labels = [(_opt_label(o), _opt_value(o)) for o in options]

    # 1. Exact match (label or value).
    for label, val in labels:
        if _norm(label) == v or _norm(val) == v:
            return {"label": label, "value": val}

    # 2. Yes/No synonyms.
    if v in _YES_WORDS:
        for label, val in labels:
            if _norm(label).startswith("yes") or _norm(val) == "yes":
                return {"label": label, "value": val}
    if v in _NO_WORDS:
        for label, val in labels:
            nl = _norm(label)
            if nl.startswith("no") or nl.startswith("i have never") or _norm(val) == "no":
                return {"label": label, "value": val}

    # 3. Substring containment in either direction.
    contains_hits: list[tuple[int, str, str]] = []
    for label, val in labels:
        nl = _norm(label)
        if not nl:
            continue
        if v in nl or nl in v:
            contains_hits.append((len(nl), label, val))
    if contains_hits:
        # Prefer the shortest containing label (more specific).
        contains_hits.sort(key=lambda t: t[0])
        _, label, val = contains_hits[0]
        return {"label": label, "value": val}

    # 4. Fuzzy ratio.
    best_ratio = 0.0
    best: Optional[tuple[str, str]] = None
    for label, val in labels:
        nl = _norm(label)
        r = SequenceMatcher(None, v, nl).ratio()
        if r > best_ratio:
            best_ratio = r
            best = (label, val)
    if best and best_ratio >= 0.55:
        return {"label": best[0], "value": best[1]}

    return None

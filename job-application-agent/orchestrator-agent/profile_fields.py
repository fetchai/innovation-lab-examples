"""Whitelist + value coercion for direct profile edits.

The LLM intent classifier returns a snake_case field name and a free-text
value. We:

- Validate the field is one the profile-agent actually tracks.
- Resolve common aliases ("linkedin_url" → "linkedin").
- Coerce the value to the right type (booleans for `needs_sponsorship`
  / `requires_visa`, plain strings otherwise).

Anything we don't recognise gets rejected with a friendly message rather
than silently dropped.
"""

from __future__ import annotations

from typing import Any, Optional


# Fields whose canonical type is `str` on UserProfile.
KNOWN_STR_FIELDS: set[str] = {
    "first_name",
    "last_name",
    "email",
    "phone",
    "city",
    "state",
    "country",
    "linkedin",
    "github",
    "portfolio",
    "twitter",
    "work_authorization",
    "gender",
    "race_ethnicity",
    "veteran_status",
    "disability_status",
}

# Fields whose canonical type is `Optional[bool]` on UserProfile.
KNOWN_BOOL_FIELDS: set[str] = {
    "needs_sponsorship",
    "requires_visa",
}

ALL_KNOWN_FIELDS: set[str] = KNOWN_STR_FIELDS | KNOWN_BOOL_FIELDS

# Common synonyms / loose forms the LLM might return.
_ALIASES: dict[str, str] = {
    "firstname": "first_name",
    "first": "first_name",
    "lastname": "last_name",
    "last": "last_name",
    "surname": "last_name",
    "name": "first_name",  # imperfect but reasonable default
    "phone_number": "phone",
    "mobile": "phone",
    "linkedin_url": "linkedin",
    "linkedin_profile": "linkedin",
    "github_url": "github",
    "github_profile": "github",
    "portfolio_url": "portfolio",
    "website": "portfolio",
    "twitter_handle": "twitter",
    "x_handle": "twitter",
    "work_auth": "work_authorization",
    "work_status": "work_authorization",
    "visa": "requires_visa",
    "sponsorship": "needs_sponsorship",
    "ethnicity": "race_ethnicity",
    "race": "race_ethnicity",
    "veteran": "veteran_status",
    "disability": "disability_status",
}


def normalise_field(name: Optional[str]) -> Optional[str]:
    """Map an LLM-supplied field name to its canonical UserProfile key,
    or None if we don't recognise it."""
    if not name:
        return None
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    if key in ALL_KNOWN_FIELDS:
        return key
    return _ALIASES.get(key)


_TRUE_WORDS = {"yes", "y", "true", "1", "yep", "yeah", "yup", "affirmative"}
_FALSE_WORDS = {"no", "n", "false", "0", "nope", "nah", "negative"}


def coerce_value(field: str, value: Any) -> tuple[bool, Any, Optional[str]]:
    """Return (ok, coerced_value, error). For boolean fields, parse common
    yes/no synonyms; for string fields, just strip whitespace."""
    if value is None:
        return False, None, "no value provided"
    if field in KNOWN_BOOL_FIELDS:
        v = str(value).strip().lower()
        if v in _TRUE_WORDS:
            return True, True, None
        if v in _FALSE_WORDS:
            return True, False, None
        return False, None, (
            f"`{field}` is a yes/no field — try `yes` or `no` (got {value!r})."
        )
    if field in KNOWN_STR_FIELDS:
        s = str(value).strip()
        if not s:
            return False, None, "value is empty after trimming"
        return True, s, None
    return False, None, f"`{field}` is not a tracked profile field"

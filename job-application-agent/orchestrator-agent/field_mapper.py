"""Field mapper - turn a Greenhouse question list into pre-filled form values.

Resolution order per question/field:

1. **Structured match**: Greenhouse uses well-known field names like
   `first_name`, `last_name`, `email`, `phone`, `resume`. We map those to
   stored `UserProfile` attributes directly. (`source="profile"`)

2. **Canned answer**: if the user has saved an answer for a free-text question
   under that exact label (or a normalized variant), use it.
   (`source="canned"`)

3. **Select-type match**: for `multi_value_single_select` / `single_select`
   fields, fuzzy-match a stored profile value (work auth, gender, etc.)
   against the allowed `values` list. (`source="profile"`)

4. **Resume + ASI:One**: for free-text fields without canned/structured matches,
   pass the full resume text to ASI:One to draft a concise answer.
   (`source="llm"`)

5. **Missing**: if none of the above produce a value, the field is added to
   `missing` and the caller can prompt the user.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from models import FilledField, MapFieldsResult, UserProfile

# Greenhouse field-name conventions we recognize.
PROFILE_FIELD_ALIASES: dict[str, str] = {
    "first_name": "first_name",
    "middle_name": "middle_name",
    "last_name": "last_name",
    "preferred_name": "preferred_name",
    "preferred_first_name": "preferred_name",
    "nickname": "preferred_name",
    "email": "email",
    "phone": "phone",
    "address": "address_line_1",
    "address_line_1": "address_line_1",
    "address1": "address_line_1",
    "street_address": "address_line_1",
    "address_line_2": "address_line_2",
    "address2": "address_line_2",
    "city": "city",
    "state": "state",
    "country": "country",
    "current_city": "city",
    "zip": "zip_code",
    "zip_code": "zip_code",
    "postal_code": "zip_code",
    "postcode": "zip_code",
    "linkedin": "linkedin",
    "linkedin_url": "linkedin",
    "github": "github",
    "github_url": "github",
    "portfolio": "portfolio",
    "website": "portfolio",
    "twitter": "twitter",
    "resume": "resume_path",  # file field
    "resume_text": "resume_text",
    "cover_letter": None,  # handled as free-text via RAG/LLM
}

# Words that strongly hint a select question is about a known profile attr.
SELECT_LABEL_MATCHERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"work\s*auth|authorized?\s*to\s*work|right\s*to\s*work", re.I), "work_authorization"),
    (re.compile(r"sponsor", re.I), "needs_sponsorship"),
    (re.compile(r"visa", re.I), "requires_visa"),
    (re.compile(r"gender", re.I), "gender"),
    (re.compile(r"(race|ethnicity)", re.I), "race_ethnicity"),
    (re.compile(r"veteran", re.I), "veteran_status"),
    (re.compile(r"disab(le|ility)", re.I), "disability_status"),
]

# Greenhouse often gives optional profile-link fields opaque names like
# `question_12345`; use the human label so known profile values still fill.
PROFILE_LABEL_MATCHERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bmiddle\s*name\b", re.I), "middle_name"),
    (re.compile(r"\bpreferred\s*(first\s*)?name\b|\bnickname\b", re.I), "preferred_name"),
    (re.compile(r"\baddress\s*(line\s*)?1\b|\bstreet\s*address\b", re.I), "address_line_1"),
    (re.compile(r"\baddress\s*(line\s*)?2\b|\bapt\b|\bsuite\b", re.I), "address_line_2"),
    (re.compile(r"\bzip\b|\bzip\s*code\b|\bpostal\s*code\b|\bpostcode\b", re.I), "zip_code"),
    (re.compile(r"\blinked\s*in\b|\blinkedin\b", re.I), "linkedin"),
    (re.compile(r"\bgithub\b|\bgit\s*hub\b", re.I), "github"),
    (re.compile(r"\bportfolio\b", re.I), "portfolio"),
    (re.compile(r"\b(personal\s+)?web\s*site\b|\bwebsite\b", re.I), "portfolio"),
    (re.compile(r"\btwitter\b|\bx\s*\(?twitter\)?\b", re.I), "twitter"),
    (re.compile(r"\bphone\b|\bmobile\b|\btelephone\b", re.I), "phone"),
    (re.compile(r"\bemail\b|\be-mail\b", re.I), "email"),
]

LLM_SYSTEM_PROMPT = (
    "You help a candidate answer a job application question. "
    "Write a concise, first-person answer (1-3 short paragraphs, max ~150 words). "
    "Ground every claim in the provided resume excerpts. "
    "Do NOT invent companies, dates, projects, technologies, or roles that are not in the excerpts. "
    "If the excerpts don't support a confident answer, reply EXACTLY with `<NEEDS_USER_INPUT>`."
)

UNKNOWN_MARKER = "<NEEDS_USER_INPUT>"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _yes_no_to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {"yes", "true", "y", "1"}:
        return True
    if s in {"no", "false", "n", "0"}:
        return False
    return None


def _fuzzy_pick_option(
    desired: Any, options: list[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    """Pick the option whose label/value best matches `desired`.

    Handles bools ("Yes"/"No"), case-insensitive substring matches, and direct
    equality. Returns the matched option dict or None.
    """
    if not options:
        return None

    if isinstance(desired, bool):
        target = "yes" if desired else "no"
        for opt in options:
            if _norm(opt.get("label", "")) == target:
                return opt
        # Some Greenhouse selects use "I am authorized..." style instead.
        for opt in options:
            label = _norm(opt.get("label", ""))
            if desired and label.startswith("yes"):
                return opt
            if not desired and label.startswith("no"):
                return opt
        return None

    target = _norm(str(desired))
    if not target:
        return None

    # Exact label match
    for opt in options:
        if _norm(opt.get("label", "")) == target:
            return opt
    # Exact value match
    for opt in options:
        if _norm(str(opt.get("value", ""))) == target:
            return opt
    # Substring (either direction)
    for opt in options:
        label = _norm(opt.get("label", ""))
        if target in label or label in target:
            return opt
    return None


class FieldMapper:
    def __init__(
        self,
        asi_api_key: Optional[str] = None,
        asi_model: str = "asi1",
    ):
        self.asi_api_key = asi_api_key or os.getenv("ASI_ONE_API_KEY")
        self.asi_model = asi_model

    # ------------------------------------------------------------------
    # LLM helper
    # ------------------------------------------------------------------

    def _llm_compose(self, question_label: str, question_desc: Optional[str], resume_text: str) -> Optional[str]:
        if not self.asi_api_key:
            return None
        try:
            from openai import OpenAI
        except ImportError:
            return None

        prompt = (
            f"Question label: {question_label}\n"
            f"Question description: {question_desc or '(none)'}\n\n"
            f"Resume:\n{resume_text[:4000]}\n\n"
            f"Write the candidate's answer now."
        )

        try:
            client = OpenAI(base_url="https://api.asi1.ai/v1", api_key=self.asi_api_key)
            resp = client.chat.completions.create(
                model=self.asi_model,
                messages=[
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400,
                temperature=0.2,
            )
            text = (resp.choices[0].message.content or "").strip()
            if not text or UNKNOWN_MARKER in text:
                return None
            return text
        except Exception:  # noqa: BLE001 - LLM is best-effort enrichment
            return None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def map_questions(
        self,
        profile: UserProfile,
        questions: list[dict[str, Any]],
        user_key: str = "me",
    ) -> MapFieldsResult:
        filled: list[FilledField] = []
        missing: list[str] = []

        for question in questions:
            label = question.get("label") or ""
            description = question.get("description")
            required = bool(question.get("required"))

            for field in question.get("fields") or []:
                name = field.get("name") or ""
                ftype = (field.get("type") or "unknown").lower()
                values = field.get("values") or []

                result = self._fill_field(
                    profile=profile,
                    user_key=user_key,
                    label=label,
                    description=description,
                    name=name,
                    ftype=ftype,
                    values=values,
                )

                if result is None:
                    if required:
                        missing.append(name or label)
                    continue

                filled.append(
                    FilledField(
                        name=name,
                        value=result["value"],
                        source=result["source"],
                        confidence=result.get("confidence", 0.8),
                        question_label=label,
                    )
                )

        return MapFieldsResult(success=True, filled=filled, missing=missing)

    # ------------------------------------------------------------------
    # Single-field resolution
    # ------------------------------------------------------------------

    def _fill_field(
        self,
        *,
        profile: UserProfile,
        user_key: str,
        label: str,
        description: Optional[str],
        name: str,
        ftype: str,
        values: list[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        # 1. Known structured-field name from Greenhouse.
        attr = PROFILE_FIELD_ALIASES.get(name)
        if attr:
            value = getattr(profile, attr, None)
            if value:
                source = "file" if attr == "resume_path" else "profile"
                return {"value": value, "source": source, "confidence": 1.0}

        # urls[Foo] convention used by Greenhouse for link sections.
        url_match = re.match(r"urls\[(.+)\]", name)
        if url_match:
            tag = url_match.group(1).strip().lower()
            mapping = {
                "linkedin": profile.linkedin,
                "github": profile.github,
                "portfolio": profile.portfolio,
                "website": profile.portfolio,
                "twitter": profile.twitter,
            }
            value = mapping.get(tag)
            if value:
                return {"value": value, "source": "profile", "confidence": 1.0}

        # Opaque optional fields (for example `question_123`) still usually
        # have clear labels like "LinkedIn Profile" or "Website".
        if ftype in {"input_text", "text", "url", "unknown"} and not values:
            for pattern, attr_name in PROFILE_LABEL_MATCHERS:
                if not pattern.search(label or ""):
                    continue
                value = getattr(profile, attr_name, None)
                if value:
                    return {"value": value, "source": "profile", "confidence": 0.95}
                break

        # 2. Canned answer keyed by label (exact then normalized).
        canned = profile.canned_answers.get(label) or profile.canned_answers.get(_norm(label))
        if canned:
            return {"value": canned, "source": "canned", "confidence": 1.0}

        # 3. Select-type fields: try to match a profile attribute against options.
        if ftype.endswith("select") or values:
            for pattern, attr_name in SELECT_LABEL_MATCHERS:
                if not pattern.search(label or ""):
                    continue
                desired = getattr(profile, attr_name, None)
                if desired is None:
                    continue
                # bools may need yes/no normalization
                if isinstance(desired, str):
                    bool_guess = _yes_no_to_bool(desired)
                    if bool_guess is not None:
                        desired = bool_guess
                opt = _fuzzy_pick_option(desired, values)
                if opt:
                    return {
                        "value": opt.get("value", opt.get("label")),
                        "source": "profile",
                        "confidence": 0.9,
                    }
                return None  # had a hint but couldn't pick a sane option

        # 4. Free-text (textarea or long input_text): full resume + LLM.
        if ftype in {"textarea", "input_text"} and label:
            if ftype == "input_text" and not re.search(r"\?|why|tell|describe|explain", label, re.I):
                return None

            if not profile.resume_text:
                return None

            answer = self._llm_compose(label, description, profile.resume_text)
            if not answer:
                return None

            return {
                "value": answer,
                "source": "llm",
                "confidence": 0.6,
            }

        return None


def map_from_dict(
    profile_dict: dict,
    questions: list[dict],
    user_key: str = "me",
) -> MapFieldsResult:
    """Convenience wrapper for callers that have a profile dict (e.g. from JSON)."""
    profile = UserProfile.model_validate(profile_dict)
    return FieldMapper().map_questions(profile, questions, user_key=user_key)


def _self_test() -> None:  # pragma: no cover - CLI helper
    import sys

    if len(sys.argv) < 3:
        print("Usage: python field_mapper.py <profile.json> <questions.json>")
        sys.exit(2)

    with open(sys.argv[1]) as f:
        profile_dict = json.load(f)
    with open(sys.argv[2]) as f:
        questions = json.load(f)

    from pathlib import Path

    result = map_from_dict(profile_dict, questions)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":  # pragma: no cover
    _self_test()

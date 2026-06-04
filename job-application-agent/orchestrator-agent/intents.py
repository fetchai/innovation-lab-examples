"""Intent classifier for the orchestrator's chat surface.

Two-stage:

1. **Regex short-circuits** for the unambiguous cases — a Greenhouse URL,
   a chat attachment, the bare word "help". These never go to the LLM.
2. **ASI:One classifier** for everything else (free-text profile edits,
   "show me my profile", small talk, "switch resume to ml-v2", etc.).

Always returns a usable `Interpretation`; never raises.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Optional

try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None  # type: ignore


ASI_ONE_BASE_URL = "https://api.asi1.ai/v1"


def _asi_one_key() -> Optional[str]:
    return os.getenv("ASI_ONE_API_KEY")


def _asi_one_model() -> str:
    return os.getenv("ASI_ONE_CHAT_MODEL", "asi1-mini")


ALLOWED_INTENTS = {
    "greet",
    "smalltalk",
    "help",
    "show_profile",
    "edit_profile",
    "upload_resume",
    "switch_resume",
    "list_resumes",
    "apply",
    "cancel",
    "noop",
}


SYSTEM_PROMPT = """You are the friendly chat assistant inside an
orchestrator agent that helps a user manage their job-search profile
and apply to jobs on Greenhouse.

On every user turn, classify intent into ONE of these:

- greet         : the user said hi / hello / how are you / etc.
- smalltalk     : casual chat that isn't a profile or apply action.
- help          : the user wants to know what they can do.
- show_profile  : "show me my profile", "what do you have on me", "whoami".
- edit_profile  : the user is updating a structured profile field (phone,
                  email, linkedin, work_authorization, gender, etc.).
                  Put `args.field` to the field name (snake_case) and
                  `args.value` to the new value.
- upload_resume : the user is offering a new resume — "here's my resume",
                  "upload my CV", "I have a new resume". (Attachments are
                  already handled deterministically, so this intent
                  triggers a "please attach the file" reply.)
- switch_resume : the user wants to make a different stored resume
                  version the active one. `args.value` is the version name.
- list_resumes  : the user wants to see which resume versions are stored.
- apply         : the user is asking to apply for a job. If they pasted a
                  Greenhouse URL it's already handled deterministically;
                  this intent triggers a "please paste the link" reply.
- cancel        : the user wants to abort whatever they were doing.
- noop          : nothing actionable.

Reply rules:
- 1-3 short, warm, casual sentences. No formal sign-offs.
- Don't list all commands unless intent=help.
- Don't dump the profile unless intent=show_profile.

Profile field names you can target with edit_profile (use these exact
snake_case names in args.field):
  first_name, last_name, email, phone, city, state, country,
  linkedin, github, portfolio, twitter,
  work_authorization, needs_sponsorship, requires_visa,
  gender, race_ethnicity, veteran_status, disability_status

Output ONLY a JSON object: {"intent": "...", "args": {...}, "reply": "..."}.
Keys other than these are ignored.
"""


@dataclass
class Interpretation:
    intent: str
    field: Optional[str] = None
    value: Optional[str] = None
    reply: str = ""
    extra: dict[str, Any] = dc_field(default_factory=dict)
    raw: Optional[str] = None


# ---------------------------------------------------------------------------
# Regex short-circuits
# ---------------------------------------------------------------------------

GREENHOUSE_URL_RE = re.compile(
    r"https?://(?:job-)?boards(?:-api)?\.greenhouse\.io/\S+",
    re.IGNORECASE,
)


def find_greenhouse_url(text: str) -> Optional[str]:
    m = GREENHOUSE_URL_RE.search(text or "")
    return m.group(0) if m else None


def short_circuit(
    user_text: str, *, has_attachment: bool = False
) -> Optional[Interpretation]:
    """Handle the obvious cases without spending a tokens on the LLM."""
    text = (user_text or "").strip()
    lower = text.lower()

    if has_attachment:
        return Interpretation(
            intent="upload_resume",
            reply="📎 Got an attachment — let me parse it as your resume.",
        )

    url = find_greenhouse_url(text)
    if url:
        return Interpretation(
            intent="apply",
            value=url,
            reply="🚀 Got it — opening that posting and starting an application.",
        )

    if lower in {"help", "?", "/help", "menu"}:
        return Interpretation(intent="help")

    if lower in {"cancel", "reset", "abort", "stop"}:
        return Interpretation(intent="cancel", reply="Okay, cancelling.")

    return None


# ---------------------------------------------------------------------------
# LLM classifier
# ---------------------------------------------------------------------------


def _heuristic_fallback(user_text: str) -> Interpretation:
    """When ASI:One is unavailable, give a warm reply and lean on the
    regex short-circuits in the caller for anything actionable."""
    text = (user_text or "").strip().lower()
    if text in {"hi", "hello", "hey", "yo", "sup", "hii"}:
        return Interpretation(
            intent="greet",
            reply=(
                "Hey 👋 I can manage your resume + profile and apply to "
                "Greenhouse jobs for you. Try `help` to see what I do."
            ),
        )
    if "profile" in text and ("show" in text or "what" in text or "who" in text):
        return Interpretation(intent="show_profile")
    return Interpretation(
        intent="smalltalk",
        reply=(
            "I'm not sure I caught that. Try `help` for what I can do, or "
            "paste a Greenhouse URL to start applying."
        ),
    )


def interpret(
    user_text: str,
    *,
    has_attachment: bool = False,
    session_summary: Optional[str] = None,
) -> Interpretation:
    """Interpret a free-text user message. Always returns an
    `Interpretation`; never raises."""
    if not user_text and not has_attachment:
        return Interpretation(intent="noop")

    sc = short_circuit(user_text, has_attachment=has_attachment)
    if sc is not None:
        return sc

    api_key = _asi_one_key()
    if not api_key or OpenAI is None:
        return _heuristic_fallback(user_text)

    user_prompt = (
        (f"Session context:\n{session_summary}\n\n" if session_summary else "")
        + f"User said: {user_text!r}\n\nReply with JSON only."
    )

    try:
        client = OpenAI(base_url=ASI_ONE_BASE_URL, api_key=api_key)
        resp = client.chat.completions.create(
            model=_asi_one_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception:  # noqa: BLE001
        return _heuristic_fallback(user_text)

    parsed = _parse_json_block(raw)
    if not parsed:
        return Interpretation(
            intent="smalltalk",
            reply=raw[:500] or _heuristic_fallback(user_text).reply,
            raw=raw,
        )

    intent = str(parsed.get("intent") or "smalltalk").lower().strip()
    if intent not in ALLOWED_INTENTS:
        intent = "smalltalk"

    args = parsed.get("args") or {}
    if not isinstance(args, dict):
        args = {}

    reply = str(parsed.get("reply") or "").strip()
    if not reply:
        reply = _heuristic_fallback(user_text).reply

    field_val = args.get("field") if isinstance(args.get("field"), str) else None
    value_val = _coerce_value(args.get("value"))

    return Interpretation(
        intent=intent,
        field=field_val,
        value=value_val,
        reply=reply,
        raw=raw,
    )


def _parse_json_block(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            obj = json.loads(fenced.group(1))
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _coerce_value(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, list):
        return ", ".join(map(str, v))
    return str(v)

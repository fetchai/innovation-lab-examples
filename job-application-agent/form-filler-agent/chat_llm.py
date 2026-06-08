"""Natural-language intent interpreter + conversational reply generator.

The form-filler still recognises explicit power-user commands deterministically
(paste a URL, `submit live`, `cancel`, `help`). Everything else — small talk,
"set my LinkedIn to ...", "what's left to do?", "show me the why-interested
answer" — flows through here.

We give ASI:One the current session context (job, filled fields, missing
fields, recent edits) and ask it to return a JSON object:

    {
      "intent": "<action>",          # answer | edit | unfill | show | show_all |
                                     # next | submit | submit_live | cancel |
                                     # help | greet | smalltalk
      "args":   { "field": "...", "value": "..." },   # only when relevant
      "reply":  "<one or two short sentences spoken to the user>"
    }

The agent dispatches the intent if it's actionable, and always sends `reply`
to the user. The result is that the agent feels like a chat partner, not a
CLI: typing "hi" gets a real greeting, "set my work auth to US Citizen" gets
treated as `answer work_authorization "US Citizen"`, and gibberish gets a
gentle, contextual nudge rather than "I didn't understand that".
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # openai is optional — agent falls back to deterministic parsing
    OpenAI = None  # type: ignore


# Read lazily inside interpret(): agent.py imports this module *before* it
# calls load_dotenv(), so capturing the env at module-load time would always
# yield None and silently disable the LLM intent classifier.
ASI_ONE_BASE_URL = "https://api.asi1.ai/v1"


def _asi_one_key() -> Optional[str]:
    return os.getenv("ASI_ONE_API_KEY")


def _asi_one_model() -> str:
    return os.getenv("ASI_ONE_CHAT_MODEL", "asi1-mini")


ALLOWED_INTENTS = {
    "greet",
    "smalltalk",
    "status",
    "help",
    "cancel",
    "show",
    "show_all",
    "show_payload",
    "next",
    "answer",
    "edit",
    "unfill",
    "compose",
    "submit",
    "submit_live",
    "noop",
}


SYSTEM_PROMPT = """You are the friendly assistant inside a job-application
agent. The user has an in-progress Greenhouse application open; you can see
the job, the fields already filled, and what is still missing. The user is
chatting with you in plain English — they are NOT typing CLI commands.

Your job, on every user turn:

1. Pick ONE intent from this list that best matches what the user wants:
   - greet      : the user said hi / hello / how are you / etc.
   - smalltalk  : casual conversation that isn't a form action.
   - status     : the user is asking where things stand, what's left, etc.
   - help       : the user wants to know what they can do here.
   - cancel     : the user wants to start over / discard this application.
   - show       : the user wants the value of one specific field. Put the
                  field's `name` (NOT its human label) in args.field.
   - show_all   : the user wants to see the whole form / preview / all fields.
   - show_payload: the user wants to see the submitter's prepared payload
                  (only relevant after a dry-run).
   - next       : the user is asking what to fill in next.
   - answer     : the user is providing a value for a MISSING field. Put the
                  exact field name in args.field, the value in args.value.
   - edit       : the user is changing the value of an ALREADY-FILLED field.
                  Use args.field (the exact name) + args.value.
   - unfill     : the user wants to clear a field. args.field is the name.
   - compose    : the user wants HELP drafting an answer (no value supplied)
                  for a free-text question — e.g. "help me answer X",
                  "draft me one", "write something for the why-figma
                  question", "can you help with this question". Put the
                  exact field `name` in args.field if the user named or
                  clearly referenced one; if they said "this" / "this one"
                  with no field, omit args.field and the agent will pick
                  the next missing one.
   - submit     : the user wants to submit (dry-run by default).
   - submit_live: the user is explicitly saying to actually post the
                  application live (e.g. "submit live", "send it for real").
   - noop       : nothing actionable; you'll handle it purely with a reply.

2. Reply in 1–3 short sentences. Be warm, casual, and human. Do NOT dump the
   full form preview unless intent is `show_all`. Do NOT list all the
   commands unless intent is `help`. Don't sign off with anything formal.

3. Important field-name rule for answer/edit/unfill: match against the
   field `name` strings exactly as listed in the form schema below. If the
   user uses a human label like "my LinkedIn", find the field whose label
   matches and use its `name`. If nothing matches, set intent=smalltalk and
   gently ask the user to clarify which field they mean.

4. Output ONLY a JSON object — no prose, no markdown fences. Keys: intent,
   args, reply. `args` may be omitted or empty when not relevant.
"""


@dataclass
class Interpretation:
    intent: str
    field: Optional[str] = None
    value: Optional[str] = None
    reply: str = ""
    raw: Optional[str] = None  # raw LLM JSON for debugging


def _summarise_session(session_ctx: dict[str, Any]) -> str:
    """Render a compact JSON-ish summary of the session for the LLM prompt."""
    lines = []
    job_title = session_ctx.get("job_title")
    job_company = session_ctx.get("job_company")
    state = session_ctx.get("state")
    if job_title:
        lines.append(f"Job: {job_title} at {job_company or 'unknown'}")
    if state:
        lines.append(f"Session state: {state}")

    filled = session_ctx.get("filled") or []
    missing = session_ctx.get("missing") or []
    if filled or missing:
        lines.append(f"Filled: {len(filled)}, Missing: {len(missing)}")

    # Show first ~12 fields with name + label + (filled value or 'MISSING').
    if session_ctx.get("schema"):
        lines.append("\nForm fields:")
        for f in session_ctx["schema"][:30]:
            name = f.get("name", "?")
            label = f.get("label", "")
            status_str = "(MISSING)" if name in missing else ""
            value_preview = ""
            for fv in filled:
                if fv.get("name") == name:
                    v = fv.get("value")
                    if isinstance(v, list):
                        v = ", ".join(map(str, v))
                    v = str(v) if v is not None else ""
                    v = v.replace("\n", " ").strip()
                    if len(v) > 60:
                        v = v[:60] + "…"
                    value_preview = f"= {v!r}"
                    break
            lines.append(f"  - name={name!r} label={label!r} {value_preview} {status_str}".rstrip())
    return "\n".join(lines).strip()


def _heuristic_fallback(user_text: str, session_ctx: dict[str, Any]) -> Interpretation:
    """Used when ASI:One is unavailable (no key) or the API call fails.
    Lightweight: just give friendly small-talk replies and let the
    deterministic command parser handle structured commands."""
    text = (user_text or "").strip().lower()
    job = session_ctx.get("job_title") or "your application"
    company = session_ctx.get("job_company")
    filled_n = len(session_ctx.get("filled") or [])
    missing_n = len(session_ctx.get("missing") or [])

    if text in {"hi", "hello", "hey", "yo", "hii", "sup"}:
        if session_ctx.get("state") == "reviewing":
            tail = (
                f"We're on **{job}**" + (f" at {company}" if company else "")
                + f" — {filled_n} filled, {missing_n} to go."
            )
            return Interpretation(
                intent="greet",
                reply=f"Hey 👋 {tail} What's next?",
            )
        return Interpretation(
            intent="greet",
            reply="Hey 👋 paste a Greenhouse job link and we'll get started.",
        )

    if "what's left" in text or "what is left" in text or "what's missing" in text:
        if missing_n:
            return Interpretation(
                intent="next",
                reply=f"{missing_n} field(s) still need an answer.",
            )
        return Interpretation(
            intent="status",
            reply="Everything's filled — say `submit` when you're ready.",
        )

    return Interpretation(
        intent="smalltalk",
        reply=(
            "I didn't quite catch that. You can paste a new Greenhouse URL, "
            "answer or edit any field in plain English, or say `submit` "
            "when you're done."
        ),
    )


def interpret(user_text: str, session_ctx: dict[str, Any]) -> Interpretation:
    """Interpret a free-text user message in the context of the current
    session. Always returns a usable Interpretation; never raises."""
    if not user_text or not user_text.strip():
        return Interpretation(intent="noop")

    api_key = _asi_one_key()
    if not api_key or OpenAI is None:
        return _heuristic_fallback(user_text, session_ctx)

    summary = _summarise_session(session_ctx)
    prompt = (
        f"Session context:\n{summary or '(no active session)'}\n\n"
        f"User said: {user_text!r}\n\n"
        f"Respond with JSON only."
    )

    try:
        client = OpenAI(base_url=ASI_ONE_BASE_URL, api_key=api_key)
        resp = client.chat.completions.create(
            model=_asi_one_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception:  # noqa: BLE001
        return _heuristic_fallback(user_text, session_ctx)

    parsed = _parse_json_block(raw)
    if not parsed:
        # Treat the entire LLM output as a plain reply.
        return Interpretation(
            intent="smalltalk",
            reply=raw[:600] or _heuristic_fallback(user_text, session_ctx).reply,
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
        reply = _heuristic_fallback(user_text, session_ctx).reply

    return Interpretation(
        intent=intent,
        field=args.get("field") if isinstance(args.get("field"), str) else None,
        value=_coerce_value(args.get("value")),
        reply=reply,
        raw=raw,
    )


def _parse_json_block(text: str) -> Optional[dict[str, Any]]:
    """Robustly pull a JSON object out of an LLM response, even if it's
    wrapped in markdown fences or has trailing prose."""
    if not text:
        return None
    # Try direct parse first.
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    # Fenced ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            obj = json.loads(fenced.group(1))
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass

    # First {...} block in the text.
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


def build_session_context(sess) -> dict[str, Any]:
    """Build the session-context dict the interpreter expects. `sess` is the
    in-memory `Session` instance from session.py — kept loose-typed here so
    chat_llm has no import cycle with session.py."""
    schema = []
    for q in (sess.questions or [])[:60]:
        for f in q.get("fields") or []:
            schema.append({"name": f.get("name"), "label": q.get("label", "")})
    return {
        "state": getattr(sess.state, "value", str(sess.state)),
        "job_title": sess.job_title,
        "job_company": sess.job_company,
        "filled": list(sess.filled or []),
        "missing": list(sess.missing_required or []),
        "schema": schema,
    }

"""Formatters for the orchestrator's chat replies.

Single source of truth for what the user sees so agent.py stays focused
on intent routing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


WELCOME = (
    "Hey 👋 I'm your job-search assistant. I can:\n\n"
    "• 📄 Manage your resume — drop a new one in chat any time and "
    "I'll re-parse it.\n"
    "• 🧠 Remember your profile — name, contact, work auth, EEO answers, "
    "you name it. Just tell me in plain English.\n"
    "• 🚀 Apply for jobs — paste any Greenhouse posting URL and I'll fill "
    "the application out for you with full visibility before you submit.\n\n"
    "Say `help` for the full list, or `show my profile` to see what I "
    "have on you already."
)


HELP = (
    "**Here's what I can do:**\n\n"
    "**Profile**\n"
    "• `show my profile` / `whoami` — see what I have stored.\n"
    "• Plain English edits, e.g. *\"my phone is +1-555-1234\"* or "
    "*\"set my work auth to US Citizen\"*.\n\n"
    "**Resume**\n"
    "• Drop a PDF/DOCX/TXT in chat — I'll parse and index it.\n"
    "• `list resumes` / `switch resume <name>` *(coming soon)*.\n\n"
    "**Apply**\n"
    "• Paste any Greenhouse URL (e.g. `https://boards.greenhouse.io/…`) "
    "and I'll start an application session.\n\n"
    "**General**\n"
    "• `cancel` — discard whatever's in progress.\n"
    "• `help` — show this list again."
)


# Display labels for structured UserProfile fields, in the order we want to
# render them.
_FIELD_LABELS: list[tuple[str, str]] = [
    ("first_name", "First name"),
    ("last_name", "Last name"),
    ("email", "Email"),
    ("phone", "Phone"),
    ("city", "City"),
    ("state", "State"),
    ("country", "Country"),
    ("linkedin", "LinkedIn"),
    ("github", "GitHub"),
    ("portfolio", "Portfolio"),
    ("twitter", "Twitter"),
    ("work_authorization", "Work authorization"),
    ("needs_sponsorship", "Needs sponsorship"),
    ("requires_visa", "Requires visa"),
    ("gender", "Gender"),
    ("race_ethnicity", "Race / ethnicity"),
    ("veteran_status", "Veteran status"),
    ("disability_status", "Disability status"),
]


def _fmt_value(v: Any) -> str:
    if v is None or v == "":
        return "_(not set)_"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return f"`{v}`"


def format_profile_summary(
    profile: Optional[dict[str, Any]],
    *,
    active_resume: Optional[str] = None,
    resume_versions: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Render the user's profile as a friendly markdown panel."""
    if not profile:
        return (
            "I don't have a profile for you yet 📭\n\n"
            "Drop your resume in chat and I'll bootstrap one — then you "
            "can tell me anything else you want me to remember."
        )

    name = " ".join(
        s for s in (profile.get("first_name"), profile.get("last_name")) if s
    )
    header = f"### 👤 {name or '_(name not set)_'}"

    lines: list[str] = [header]
    contact = []
    if profile.get("email"):
        contact.append(f"📧 {profile['email']}")
    if profile.get("phone"):
        contact.append(f"📞 {profile['phone']}")
    if contact:
        lines.append("  ·  ".join(contact))

    # Resume section
    resume_path = profile.get("resume_path")
    indexed = profile.get("resume_indexed")
    if resume_path:
        fname = resume_path.rsplit("/", 1)[-1]
        rl = f"📎 Active resume: `{fname}`"
        if active_resume:
            rl += f" (version: `{active_resume}`)"
        if indexed:
            rl += "  · indexed ✓"
        lines.append(rl)
        if resume_versions and len(resume_versions) > 1:
            others = [
                v["name"] for v in resume_versions if v.get("name") != active_resume
            ]
            if others:
                lines.append(f"Other versions: {', '.join(f'`{n}`' for n in others)}")
    else:
        lines.append("📎 _No resume on file yet — drop one in chat to bootstrap._")

    lines.append("")
    lines.append("**Structured fields**")
    for key, label in _FIELD_LABELS:
        if key in ("first_name", "last_name", "email", "phone"):
            continue
        lines.append(f"• {label}: {_fmt_value(profile.get(key))}")

    canned = profile.get("canned_answers") or {}
    if canned:
        lines.append("")
        lines.append(f"**Canned answers saved:** {len(canned)}")
        for k in list(canned.keys())[:5]:
            preview = canned[k]
            if isinstance(preview, str) and len(preview) > 60:
                preview = preview[:60] + "…"
            lines.append(f"• _{k}_ → `{preview}`")
        if len(canned) > 5:
            lines.append(f"• …and {len(canned) - 5} more")

    updated = profile.get("updated_at")
    if updated:
        lines.append("")
        lines.append(f"_Last updated: {_human_when(updated)}_")

    return "\n".join(lines)


def _human_when(iso: str) -> str:
    """Format an ISO timestamp as a friendly relative-ish string."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return iso
    now = datetime.now(timezone.utc)
    delta = now - dt
    if delta.total_seconds() < 60:
        return "just now"
    mins = delta.total_seconds() // 60
    if mins < 60:
        return f"{int(mins)}m ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{int(hrs)}h ago"
    days = hrs // 24
    if days < 7:
        return f"{int(days)}d ago"
    return dt.strftime("%Y-%m-%d")


def format_edit_confirmation(field: str, value: str) -> str:
    return f"✓ Saved `{field}` → `{value}`. I'll remember this for next time."


def format_field_unknown(field: str) -> str:
    return (
        f"Hmm, I don't have a profile slot called `{field}`. Try "
        f"`show my profile` to see what fields I track."
    )


def format_error(message: str) -> str:
    return f"⚠️ {message}"

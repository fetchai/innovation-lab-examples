"""Formatters for the orchestrator's chat replies.

Single source of truth for what the user sees so agent.py stays focused
on intent routing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from uagents_core.contrib.protocols.chat.cards import (
    ButtonAction,
    CarouselBadge,
    CarouselCardPayload,
    CarouselItem,
    CtaAction,
    CustomCardPayload,
    DetailCardPayload,
    DetailSummaryRow,
    FormCardPayload,
    FormField,
    FormFieldOption,
    HeadingNode,
    ListItem,
    ListNode,
    SectionNode,
    TextNode,
)


# ---------------------------------------------------------------------------
# Profile section schema — used by both the list card and the section forms.
# ---------------------------------------------------------------------------

SECTIONS = ["personal", "links", "work_auth", "eeo", "resume", "answers"]

_PERSONAL_FIELDS = [
    ("first_name", "First name", "text", True),
    ("last_name", "Last name", "text", True),
    ("email", "Email", "email", True),
    ("phone", "Phone", "text", False),
    ("city", "City", "text", False),
    ("state", "State / region", "text", False),
    ("country", "Country", "text", False),
]

_LINK_FIELDS = [
    ("linkedin", "LinkedIn URL", "text", False),
    ("github", "GitHub URL", "text", False),
    ("portfolio", "Portfolio URL", "text", False),
    ("twitter", "Twitter / X URL", "text", False),
]

_WORK_AUTH_SELECT = [
    ("US Citizen", "US Citizen"),
    ("Permanent Resident", "Permanent Resident / Green Card"),
    ("H1B", "H1B"),
    ("F1 OPT", "F1 OPT / CPT"),
    ("TN", "TN"),
    ("Other", "Other"),
]

_GENDER_SELECT = [
    ("Male", "Male"),
    ("Female", "Female"),
    ("Non-binary", "Non-binary"),
    ("Prefer not to say", "Prefer not to say"),
]

_RACE_SELECT = [
    ("Asian", "Asian"),
    ("Black or African American", "Black or African American"),
    ("Hispanic or Latino", "Hispanic or Latino"),
    ("White", "White"),
    ("Two or more races", "Two or more races"),
    ("Prefer not to say", "Prefer not to say"),
]

_VETERAN_SELECT = [
    ("I am not a protected veteran", "I am not a protected veteran"),
    ("I am a protected veteran", "I am a protected veteran"),
    ("Prefer not to say", "Prefer not to say"),
]

_DISABILITY_SELECT = [
    ("Yes", "Yes, I have a disability"),
    ("No", "No, I do not have a disability"),
    ("Prefer not to say", "Prefer not to say"),
]


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


_EMPTY = "—"


def _has(v: Any) -> bool:
    return v not in (None, "", [], {})


def _yn(v: Any) -> Optional[str]:
    if v is True:
        return "Yes"
    if v is False:
        return "No"
    return None


def _join(parts: list[Optional[str]], sep: str = "  ·  ") -> str:
    return sep.join(p for p in parts if p)


def _ok_badge(ok: bool) -> CarouselBadge:
    return CarouselBadge(
        label="Complete" if ok else "Needs info",
        variant="success" if ok else "warning",
    )


def build_profile_carousel(
    profile: Optional[dict[str, Any]],
    *,
    active_resume: Optional[str] = None,
    resume_versions: Optional[list[dict[str, Any]]] = None,
) -> CarouselCardPayload:
    """Profile as a swipeable CarouselCardPayload — one item per category."""

    if not profile:
        return CarouselCardPayload(
            title="👤 Profile",
            subtitle="No profile yet — drop your resume in chat to bootstrap.",
            items=[
                CarouselItem(
                    id="bootstrap",
                    title="Get started",
                    subtitle="Upload a resume and I'll extract everything I can.",
                    primary_cta=CtaAction(
                        label="Upload resume",
                        selection={"action": "upload_resume"},
                        primary=True,
                    ),
                )
            ],
        )

    p = profile
    name = " ".join(s for s in (p.get("first_name"), p.get("last_name")) if s)
    header_name = name or "Profile"
    updated = p.get("updated_at")
    subtitle = f"Last updated {_human_when(updated)}" if updated else None

    items: list[CarouselItem] = []

    # ---- 1) Personal ----
    loc = ", ".join(
        s for s in (p.get("city"), p.get("state"), p.get("country")) if s
    )
    personal_sub = _join([
        name or None, p.get("email"), p.get("phone"), loc or None,
    ]) or "Tell me your name and contact info"
    items.append(CarouselItem(
        id="personal",
        title="👤  Personal",
        subtitle=personal_sub,
        primary_cta=CtaAction(
            label="Edit",
            selection={"action": "edit_profile", "section": "personal"},
            primary=True,
        ),
    ))

    # ---- 2) Resume ----
    resume_path = p.get("resume_path")
    if resume_path:
        fname = resume_path.rsplit("/", 1)[-1]
        rbits = [fname]
        if active_resume:
            rbits.append(active_resume)
        if p.get("resume_indexed"):
            rbits.append("indexed ✓")
        resume_sub = "  ·  ".join(rbits)
    else:
        resume_sub = "Not uploaded — drop a PDF or DOCX in chat"
    items.append(CarouselItem(
        id="resume",
        title="📎  Resume",
        subtitle=resume_sub,
        primary_cta=CtaAction(
            label="Replace resume",
            selection={"action": "upload_resume"},
            primary=True,
        ),
    ))

    # ---- 3) Links ----
    link_pairs = [
        ("LinkedIn", p.get("linkedin")),
        ("GitHub", p.get("github")),
        ("Portfolio", p.get("portfolio")),
        ("Twitter", p.get("twitter")),
    ]
    set_links = [(k, v) for k, v in link_pairs if _has(v)]
    if set_links:
        link_sub = f"{len(set_links)} of {len(link_pairs)} set  ·  " + ", ".join(
            k for k, _ in set_links
        )
    else:
        link_sub = "Add LinkedIn, GitHub, portfolio, or Twitter"
    items.append(CarouselItem(
        id="links",
        title="🔗  Links",
        subtitle=link_sub,
        primary_cta=CtaAction(
            label="Edit links",
            selection={"action": "edit_profile", "section": "links"},
            primary=True,
        ),
    ))

    # ---- 4) Work authorization ----
    wa_bits = []
    if p.get("work_authorization"):
        wa_bits.append(str(p["work_authorization"]))
    if p.get("needs_sponsorship") is not None:
        wa_bits.append(
            "needs sponsorship" if p["needs_sponsorship"] else "no sponsorship"
        )
    if p.get("requires_visa") is not None:
        wa_bits.append(
            "visa required" if p["requires_visa"] else "no visa"
        )
    wa_sub = "  ·  ".join(wa_bits) if wa_bits else "Status, sponsorship, visa — not set"
    items.append(CarouselItem(
        id="work_auth",
        title="🛂  Work authorization",
        subtitle=wa_sub,
        primary_cta=CtaAction(
            label="Edit work auth",
            selection={"action": "edit_profile", "section": "work_auth"},
            primary=True,
        ),
    ))

    # ---- 5) Demographics / EEO ----
    eeo_pairs = [
        ("Gender", p.get("gender")),
        ("Race", p.get("race_ethnicity")),
        ("Veteran", p.get("veteran_status")),
        ("Disability", p.get("disability_status")),
    ]
    set_eeo = [(k, v) for k, v in eeo_pairs if _has(v)]
    eeo_sub = (
        f"{len(set_eeo)} of {len(eeo_pairs)} answered  ·  "
        + ", ".join(k for k, _ in set_eeo)
        if set_eeo
        else "Optional EEO questions — answer when ready"
    )
    items.append(CarouselItem(
        id="eeo",
        title="📊  Demographics",
        subtitle=eeo_sub,
        primary_cta=CtaAction(
            label="Edit demographics",
            selection={"action": "edit_profile", "section": "eeo"},
            primary=True,
        ),
    ))

    # ---- 6) Saved answers ----
    canned = p.get("canned_answers") or {}
    if canned:
        preview_key = next(iter(canned))
        preview_q = preview_key if len(preview_key) <= 60 else preview_key[:59] + "…"
        canned_sub = f"{len(canned)} saved  ·  e.g. “{preview_q}”"
    else:
        canned_sub = "No saved answers yet — I'll remember tricky ones for you"
    items.append(CarouselItem(
        id="answers",
        title="💬  Saved answers",
        subtitle=canned_sub,
        primary_cta=CtaAction(
            label="View answers",
            selection={"action": "show_canned_answers"},
            primary=True,
        ),
    ))

    return CarouselCardPayload(
        title=f"👤 {header_name}",
        subtitle=subtitle,
        items=items,
    )


def _section_summary(
    section: str,
    profile: dict[str, Any],
    *,
    active_resume: Optional[str] = None,
) -> str:
    """One-line muted summary shown under each list item."""
    p = profile

    if section == "personal":
        loc = ", ".join(s for s in (p.get("city"), p.get("state"), p.get("country")) if s)
        bits = [p.get("email"), p.get("phone"), loc or None]
        return _join(bits) or "Tap to add contact details."

    if section == "links":
        names = [
            n for n, k in [("LinkedIn", "linkedin"), ("GitHub", "github"),
                            ("Portfolio", "portfolio"), ("Twitter", "twitter")]
            if _has(p.get(k))
        ]
        return ", ".join(names) if names else "No links saved yet."

    if section == "work_auth":
        bits = []
        if p.get("work_authorization"):
            bits.append(str(p["work_authorization"]))
        if p.get("needs_sponsorship") is not None:
            bits.append("needs sponsorship" if p["needs_sponsorship"] else "no sponsorship")
        if p.get("requires_visa") is not None:
            bits.append("visa required" if p["requires_visa"] else "no visa")
        return _join(bits) or "Status, sponsorship, visa — not set."

    if section == "eeo":
        set_n = sum(
            1 for k in ("gender", "race_ethnicity", "veteran_status", "disability_status")
            if _has(p.get(k))
        )
        return f"{set_n} of 4 optional EEO questions answered."

    if section == "resume":
        if p.get("resume_path"):
            fname = p["resume_path"].rsplit("/", 1)[-1]
            tag = "indexed ✓" if p.get("resume_indexed") else "not indexed"
            v = f"  ·  {active_resume}" if active_resume else ""
            return f"{fname}{v}  ·  {tag}"
        return "Not uploaded — drop a PDF or DOCX in chat."

    if section == "answers":
        canned = p.get("canned_answers") or {}
        return (
            f"{len(canned)} reusable answer{'s' if len(canned) != 1 else ''} saved."
            if canned else "Nothing saved yet — I'll remember tricky answers for you."
        )

    return ""


def _section_meta(section: str) -> tuple[str, str]:
    """(emoji-title, hint)."""
    return {
        "personal": ("👤  Personal", "Name, email, phone, location."),
        "links":    ("🔗  Links", "LinkedIn, GitHub, portfolio, Twitter."),
        "work_auth": ("🛂  Work authorization", "Status, sponsorship, visa."),
        "eeo":      ("📊  Demographics (EEO)", "Optional EEO fields."),
        "resume":   ("📎  Resume", "Upload or replace your resume."),
        "answers":  ("💬  Saved answers", "Reusable answers I've remembered."),
    }[section]


def build_profile_list_card(
    profile: Optional[dict[str, Any]],
    *,
    active_resume: Optional[str] = None,
    resume_versions: Optional[list[dict[str, Any]]] = None,  # noqa: ARG001
) -> CustomCardPayload:
    """Profile overview as a tappable list card. Each row opens a form
    card for that section (handled by the agent's card-response handler)."""

    if not profile:
        return CustomCardPayload(root=SectionNode(
            type="section",
            title="👤 Profile",
            subtitle="No profile yet — drop your resume in chat to bootstrap.",
            children=[TextNode(
                type="text",
                value="Upload a PDF/DOCX and I'll extract everything I can.",
                style="muted",
            )],
        ))

    p = profile
    name = " ".join(s for s in (p.get("first_name"), p.get("last_name")) if s)
    updated = p.get("updated_at")
    subtitle = (
        f"Last updated {_human_when(updated)}  ·  tap any section to edit"
        if updated else "Tap any section to edit"
    )

    list_items: list[ListItem] = []
    for sec in SECTIONS:
        title, _ = _section_meta(sec)
        summary = _section_summary(sec, p, active_resume=active_resume)
        list_items.append(ListItem(
            children=[
                HeadingNode(type="heading", value=title, level=3),
                TextNode(type="text", value=summary, style="muted"),
            ],
            action=ButtonAction(selection={"section": sec}),
        ))

    return CustomCardPayload(root=SectionNode(
        type="section",
        title=f"👤 {name or 'Profile'}",
        subtitle=subtitle,
        children=[ListNode(type="list", items=list_items)],
    ))


# ---------------------------------------------------------------------------
# Per-section FORM cards. The agent serves one of these when the user taps
# a list row on the profile overview.
# ---------------------------------------------------------------------------


def _opt(value: str, label: str) -> FormFieldOption:
    return FormFieldOption(value=value, label=label)


def _placeholder(profile: dict[str, Any], key: str) -> Optional[str]:
    v = profile.get(key)
    if v in (None, ""):
        return None
    if isinstance(v, bool):
        return "currently: yes" if v else "currently: no"
    return f"currently: {v}"


def _simple_fields(
    profile: dict[str, Any],
    spec: list[tuple[str, str, str, bool]],
) -> list[FormField]:
    out: list[FormField] = []
    for name, label, kind, required in spec:
        out.append(FormField(
            name=name,
            kind=kind,
            label=label,
            required=required,
            placeholder=_placeholder(profile, name),
        ))
    return out


def _select_field(
    profile: dict[str, Any],
    name: str,
    label: str,
    options: list[tuple[str, str]],
    *,
    required: bool = False,
) -> FormField:
    return FormField(
        name=name,
        kind="select",
        label=label,
        required=required,
        options=[_opt(v, l) for v, l in options],
        placeholder=_placeholder(profile, name),
    )


def build_section_form(
    section: str,
    profile: Optional[dict[str, Any]],
) -> Optional[FormCardPayload]:
    """Form card for a single profile section. Returns None when the
    section isn't form-editable (resume = upload, answers = list view)."""
    p = profile or {}

    if section == "personal":
        return FormCardPayload(
            title="👤 Personal details",
            fields=_simple_fields(p, _PERSONAL_FIELDS),
            submit_cta=CtaAction(
                label="Save personal",
                selection={"section": "personal", "submitted": True},
                primary=True,
            ),
        )

    if section == "links":
        return FormCardPayload(
            title="🔗 Links",
            fields=_simple_fields(p, _LINK_FIELDS),
            submit_cta=CtaAction(
                label="Save links",
                selection={"section": "links", "submitted": True},
                primary=True,
            ),
        )

    if section == "work_auth":
        return FormCardPayload(
            title="🛂 Work authorization",
            fields=[
                _select_field(p, "work_authorization", "Authorization status",
                              _WORK_AUTH_SELECT, required=True),
                FormField(name="needs_sponsorship", kind="checkbox",
                          label="I will need visa sponsorship now or in the future",
                          placeholder=_placeholder(p, "needs_sponsorship")),
                FormField(name="requires_visa", kind="checkbox",
                          label="I currently require a visa to work",
                          placeholder=_placeholder(p, "requires_visa")),
            ],
            submit_cta=CtaAction(
                label="Save work authorization",
                selection={"section": "work_auth", "submitted": True},
                primary=True,
            ),
        )

    if section == "eeo":
        return FormCardPayload(
            title="📊 Demographics (optional)",
            fields=[
                _select_field(p, "gender", "Gender", _GENDER_SELECT),
                _select_field(p, "race_ethnicity", "Race / ethnicity", _RACE_SELECT),
                _select_field(p, "veteran_status", "Veteran status", _VETERAN_SELECT),
                _select_field(p, "disability_status", "Disability status",
                              _DISABILITY_SELECT),
            ],
            submit_cta=CtaAction(
                label="Save demographics",
                selection={"section": "eeo", "submitted": True},
                primary=True,
            ),
        )

    # resume / answers handled by the agent with non-form replies.
    return None


def _fmt_bool(v: Any) -> Optional[str]:
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if v in (None, ""):
        return None
    return str(v)


def _push(rows: list[DetailSummaryRow], label: str, v: Any) -> None:
    """Append a row only if `v` is set. Keeps the card tight."""
    text = _fmt_bool(v)
    if text:
        rows.append(DetailSummaryRow(label=label, value=text))


def build_profile_card(
    profile: Optional[dict[str, Any]],
    *,
    active_resume: Optional[str] = None,
    resume_versions: Optional[list[dict[str, Any]]] = None,
) -> DetailCardPayload:
    """Profile as a DetailCardPayload. We set `preferred_drawer_width_px`
    on the wrapper so the chat client pops it into its side drawer
    (the same surface as image 4's `Task details`)."""

    if not profile:
        return DetailCardPayload(
            title="👤 Profile",
            summary_rows=[
                DetailSummaryRow(
                    label="Status",
                    value="No profile yet — drop a resume in chat to bootstrap.",
                ),
            ],
            ctas=[CtaAction(label="Upload resume",
                            selection={"action": "upload_resume"})],
        )

    p = profile
    name = " ".join(s for s in (p.get("first_name"), p.get("last_name")) if s)
    title = f"👤 {name}" if name else "👤 Profile"

    rows: list[DetailSummaryRow] = []

    # ---- Contact ----
    _push(rows, "Email", p.get("email"))
    _push(rows, "Phone", p.get("phone"))

    # ---- Resume ----
    resume_path = p.get("resume_path")
    if resume_path:
        fname = resume_path.rsplit("/", 1)[-1]
        rv = fname
        if active_resume:
            rv += f"  ·  {active_resume}"
        if p.get("resume_indexed"):
            rv += "  ·  indexed ✓"
        rows.append(DetailSummaryRow(label="Resume", value=rv))
        if resume_versions and len(resume_versions) > 1:
            others = [
                v["name"] for v in resume_versions
                if v.get("name") and v.get("name") != active_resume
            ]
            if others:
                rows.append(DetailSummaryRow(
                    label="Other resumes", value=", ".join(others)
                ))
    else:
        rows.append(DetailSummaryRow(label="Resume", value="Not uploaded"))

    # ---- Location ----
    loc = ", ".join(
        s for s in (p.get("city"), p.get("state"), p.get("country")) if s
    )
    if loc:
        rows.append(DetailSummaryRow(label="Location", value=loc))

    # ---- Links (one row per set link only) ----
    _push(rows, "LinkedIn", p.get("linkedin"))
    _push(rows, "GitHub", p.get("github"))
    _push(rows, "Portfolio", p.get("portfolio"))
    _push(rows, "Twitter", p.get("twitter"))

    # ---- Work authorization (single combined line if anything is set) ----
    wa_bits = []
    if p.get("work_authorization"):
        wa_bits.append(str(p["work_authorization"]))
    if p.get("needs_sponsorship") is not None:
        wa_bits.append(
            "needs sponsorship" if p["needs_sponsorship"] else "no sponsorship"
        )
    if p.get("requires_visa") is not None:
        wa_bits.append("visa required" if p["requires_visa"] else "no visa")
    if wa_bits:
        rows.append(DetailSummaryRow(
            label="Work authorization", value="  ·  ".join(wa_bits)
        ))

    # ---- EEO (single combined line of whatever is set) ----
    eeo_pairs = [
        ("Gender", p.get("gender")),
        ("Race / ethnicity", p.get("race_ethnicity")),
        ("Veteran", p.get("veteran_status")),
        ("Disability", p.get("disability_status")),
    ]
    eeo_filled = [f"{k}: {v}" for k, v in eeo_pairs if v]
    if eeo_filled:
        rows.append(DetailSummaryRow(
            label="Demographics", value="  ·  ".join(eeo_filled)
        ))

    # ---- Canned answers (count + preview question) ----
    canned = p.get("canned_answers") or {}
    if canned:
        preview_key = next(iter(canned))
        preview_q = preview_key if len(preview_key) <= 60 else preview_key[:59] + "…"
        rows.append(DetailSummaryRow(
            label=f"Saved answers · {len(canned)}",
            value=f"e.g. “{preview_q}”",
        ))

    updated = p.get("updated_at")
    if updated:
        rows.append(DetailSummaryRow(label="Last updated", value=_human_when(updated)))

    return DetailCardPayload(
        title=title,
        summary_rows=rows,
        ctas=[
            CtaAction(label="Edit profile",
                      selection={"action": "edit_profile"}),
            CtaAction(label="Replace resume",
                      selection={"action": "upload_resume"}),
        ],
    )


def _short(v: Any, n: int = 60) -> str:
    s = str(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def format_profile_summary(
    profile: Optional[dict[str, Any]],
    *,
    active_resume: Optional[str] = None,
    resume_versions: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Render the user's profile as a clean, sectioned markdown panel."""
    if not profile:
        return (
            "### 👤 Profile\n\n"
            "_No profile yet._ Drop your resume in chat and I'll bootstrap "
            "one — then tell me anything else you want me to remember."
        )

    p = profile

    # ---- Header ----
    name = " ".join(s for s in (p.get("first_name"), p.get("last_name")) if s)
    lines: list[str] = [f"### 👤 {name or '_(name not set)_'}"]

    contact = []
    if p.get("email"):
        contact.append(f"📧 {p['email']}")
    if p.get("phone"):
        contact.append(f"📞 {p['phone']}")
    if contact:
        lines.append("  ·  ".join(contact))

    def section(title: str, body_lines: list[str]) -> None:
        body = [b for b in body_lines if b]
        if not body:
            return
        lines.append("")
        lines.append("---")
        lines.append(f"**{title}**")
        lines.extend(body)

    # ---- Resume ----
    resume_path = p.get("resume_path")
    indexed = p.get("resume_indexed")
    resume_body: list[str] = []
    if resume_path:
        fname = resume_path.rsplit("/", 1)[-1]
        line = f"📎 `{fname}`"
        if active_resume:
            line += f"  ·  version `{active_resume}`"
        if indexed:
            line += "  ·  indexed ✓"
        resume_body.append(line)
        if resume_versions and len(resume_versions) > 1:
            others = [
                v["name"] for v in resume_versions
                if v.get("name") and v.get("name") != active_resume
            ]
            if others:
                resume_body.append(
                    "Other versions: " + ", ".join(f"`{n}`" for n in others)
                )
    else:
        resume_body.append("_No resume on file — drop one in chat to bootstrap._")
    section("RESUME", resume_body)

    # ---- Location ----
    loc_parts = [p.get("city"), p.get("state"), p.get("country")]
    loc_str = ", ".join(s for s in loc_parts if s)
    section("LOCATION", [f"📍 {loc_str}" if loc_str else "_(not set)_"])

    # ---- Links ----
    link_specs = [
        ("LinkedIn", "linkedin", "🔗"),
        ("GitHub", "github", "🐙"),
        ("Portfolio", "portfolio", "🌐"),
        ("Twitter", "twitter", "🐦"),
    ]
    link_lines = []
    for label, key, icon in link_specs:
        v = p.get(key)
        if v:
            link_lines.append(f"{icon} {label} — {v}")
    if not link_lines:
        link_lines.append("_(none set)_")
    section("LINKS", link_lines)

    # ---- Work authorization ----
    wa_lines = [
        f"Status — {_fmt_value(p.get('work_authorization'))}",
        f"Needs sponsorship — {_fmt_value(p.get('needs_sponsorship'))}",
        f"Requires visa — {_fmt_value(p.get('requires_visa'))}",
    ]
    section("WORK AUTHORIZATION", wa_lines)

    # ---- EEO / Demographics ----
    eeo_lines = [
        f"Gender — {_fmt_value(p.get('gender'))}",
        f"Race / ethnicity — {_fmt_value(p.get('race_ethnicity'))}",
        f"Veteran status — {_fmt_value(p.get('veteran_status'))}",
        f"Disability status — {_fmt_value(p.get('disability_status'))}",
    ]
    section("DEMOGRAPHICS (EEO)", eeo_lines)

    # ---- Canned answers ----
    canned = p.get("canned_answers") or {}
    if canned:
        canned_lines = []
        for k in list(canned.keys())[:5]:
            q = _short(k, 70)
            a = _short(canned[k], 60)
            canned_lines.append(f"• _{q}_ → `{a}`")
        if len(canned) > 5:
            canned_lines.append(f"…and {len(canned) - 5} more")
        section(f"SAVED ANSWERS  ·  {len(canned)}", canned_lines)

    updated = p.get("updated_at")
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

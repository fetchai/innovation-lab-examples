"""Format chat messages for the form-filler agent.

Single source of truth for what the user sees so the agent.py file stays
focused on orchestration. All formatters return plain strings — the caller
wraps them in `ChatMessage(content=[TextContent(...)])`.
"""

from __future__ import annotations

from typing import Any

from form_session import Session


# Width tuned for typical chat clients (mono-ish columns ~64 chars wide).
PANEL_WIDTH = 62
SOURCE_GLYPH = {
    "profile": "👤",
    "canned": "💾",
    "rag": "🧠",
    "llm": "✨",
    "file": "📎",
    "default": "🎯",
    "user": "✏️ ",
    "manual": "✏️ ",
}


def _glyph(source: str) -> str:
    return SOURCE_GLYPH.get(source, "•")


def _truncate(text: str, limit: int) -> str:
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def format_job_summary(sess: Session) -> str:
    q_count = len(sess.questions)
    file_count = sum(
        1
        for q in sess.questions
        for f in (q.get("fields") or [])
        if (f.get("type") or "").lower() in {"input_file", "file"}
    )
    lines = [
        f"📄 **{sess.job_title or 'Job posting'}**",
        f"Company: {sess.job_company or '—'}  ·  Location: {sess.job_location or '—'}",
        f"Application has {q_count} question{'s' if q_count != 1 else ''} "
        f"({file_count} file upload{'s' if file_count != 1 else ''}, "
        f"{q_count - file_count} form field{'s' if (q_count - file_count) != 1 else ''}).",
    ]
    return "\n".join(lines)


def format_panel_compact(sess: Session) -> str:
    """Single-line summary of the form state — used as a caption beside
    the live-fill screenshot so the chat doesn't double up on form
    information. The screenshot IS the form; this is just the score."""
    filled = sess.filled or []
    missing = sess.missing_required or []
    not_in_filled = [m for m in missing if not any(f["name"] == m for f in filled)]
    total = len(filled) + len(not_in_filled)

    head = f"**{len(filled)}/{total} fields filled**"
    if missing:
        labels: list[str] = []
        for name in missing[:5]:
            labels.append(_missing_label(sess, name))
        more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        return (
            f"{head} · **Still need:** {', '.join(labels)}{more}\n"
            f"_Reply in plain English (e.g. \"my work auth is US Citizen\") to fill anything. "
            f"Say `submit` when ready._"
        )
    return f"{head} · 🎉 _All required fields filled — say `submit` whenever you're ready._"


def _value_display(value: Any, ftype: str) -> str:
    ftype = (ftype or "").lower()
    if ftype in {"input_file", "file"}:
        return f"📎 `{value}`"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if value in (None, ""):
        return "_(empty)_"
    s = str(value).replace("\n", " ").strip()
    return f"`{_truncate(s, 80)}`"


def _question_and_field(sess: Session, name: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for q in sess.questions:
        for f in q.get("fields") or []:
            if f.get("name") == name:
                return q, f
    return None, None


def _missing_label(sess: Session, name: str) -> str:
    q, _ = _question_and_field(sess, name)
    return (q or {}).get("label") or name


def format_form_panel(sess: Session) -> str:
    """Render the live application as a form-like markdown panel — grouped
    by question, with the actual question text, value, and a per-field
    status badge. Designed to look like an HTML `<form>` rendered into
    chat so the user has real visibility without depending on screenshots."""
    questions = sess.questions or []
    filled_by_name = {f.get("name"): f for f in (sess.filled or [])}
    missing = set(sess.missing_required or [])

    if not questions:
        return "_(no form fields parsed yet)_"

    filled_count = len(sess.filled or [])
    missing_count = len(missing)
    total_count = filled_count + sum(
        1 for n in missing if n not in filled_by_name
    )

    header = [
        f"### 📋 {sess.job_title or 'Application form'}",
        f"_{sess.job_company or ''}_  ·  **{filled_count}/{total_count} filled**",
        "",
        "---",
    ]

    body: list[str] = []
    for idx, q in enumerate(questions, start=1):
        label = (q.get("label") or "").strip()
        required = bool(q.get("required"))
        fields = q.get("fields") or []
        req_mark = " *" if required else ""
        body.append(f"**{idx}. {label or '(no label)'}**{req_mark}")

        for fld in fields:
            name = fld.get("name") or "?"
            ftype = (fld.get("type") or "").lower()
            filled = filled_by_name.get(name)
            if filled is not None and filled.get("value") not in (None, ""):
                badge = "✅"
                src = filled.get("source") or ""
                src_glyph = _glyph(src) if src else ""
                value_md = _value_display(filled.get("value"), ftype)
                body.append(
                    f"  - {badge} `{name}` → {value_md}  {src_glyph}_{src}_"
                )
            elif name in missing:
                body.append(
                    f"  - ⚠️  `{name}` — _required; needs your input_  "
                    f"(reply: `answer {name} <value>`)"
                )
            else:
                body.append(f"  - ◻️  `{name}` — _(optional, blank)_")

        body.append("")

    footer = ["---"]
    if missing_count:
        footer.append(
            f"_{missing_count} required field"
            f"{'s' if missing_count != 1 else ''} still need"
            f"{'' if missing_count != 1 else 's'} your input._ Say `next` for "
            "the next missing field, or just answer in plain English."
        )
    else:
        footer.append(
            "🎉 _All required fields are filled — say `submit` whenever you're ready._"
        )

    return "\n".join(header + body + footer)


def format_panel(sess: Session) -> str:
    """Detailed form-preview panel (filled + missing).

    Reserved for explicit `show all` requests — the default flow uses the
    live-fill screenshot + `format_panel_compact` because that's a much
    better chat UX than dumping every field as text.
    """
    filled = sess.filled
    missing = sess.missing_required
    not_in_filled = [m for m in missing if not any(f["name"] == m for f in filled)]
    total = len(filled) + len(not_in_filled)

    lines = [f"**Form preview — {len(filled)}/{total} filled**", ""]

    for f in filled:
        name = f.get("name", "?")
        value = f.get("value")
        source = f.get("source", "")
        conf = f.get("confidence")
        ftype = (f.get("ftype") or "").lower()

        if ftype in {"input_file", "file"}:
            display = f"📎 {value}"
        elif isinstance(value, list):
            display = ", ".join(str(v) for v in value)
        else:
            display = str(value) if value is not None else ""

        display = _truncate(display.replace("\n", " ").strip(), 50)
        meta = f"[{source}"
        if isinstance(conf, (int, float)) and source not in ("file", "user"):
            meta += f" {conf:.2f}"
        meta += "]"

        lines.append(
            f"  ✅ `{name}` = {display}  {meta}"
        )

    if not_in_filled:
        if filled:
            lines.append("")
        for name in not_in_filled:
            q_label = _missing_label(sess, name)
            label_hint = f" — _{_truncate(q_label, 60)}_" if q_label else ""
            lines.append(f"  ⚠️  `{name}` — **required; needs your input**{label_hint}")

    lines.append("")
    if missing:
        lines.append(
            f"_{len(missing)} required field{'s' if len(missing) != 1 else ''} "
            f"still need{'' if len(missing) != 1 else 's'} your input._"
        )
    else:
        lines.append("🎉 _All required fields are filled._")
    return "\n".join(lines)


def format_commands_hint(have_missing: bool) -> str:
    submit_line = (
        "• `submit`                 — finalize (dry-run by default;\n"
        "                             `submit live` to actually post)"
    )
    lines = [
        "**Commands:**",
        "• `show <name>`            — full value of one field",
        "• `answer <name> <value>`  — fill a missing field",
        "• `edit <name> <value>`    — change a filled value",
        "• `unfill <name>`          — clear a field",
        "• `next`                   — show the next missing field",
        submit_line,
        "• `cancel`                 — discard this session",
    ]
    if not have_missing:
        lines.insert(1, "_All required fields are filled. Review and `submit` when ready._\n")
    return "\n".join(lines)


def format_field_detail(sess: Session, name: str) -> str:
    idx = sess.index_of(name)
    if idx < 0:
        if name in sess.missing_required:
            q_label = _missing_label(sess, name)
            return (
                f"⚠️ **{name}** — required field, not yet filled.\n"
                f"Question label: {q_label or '(none)'}\n"
                f"To fill: `answer {name} <value>`"
            )
        return f"No field named `{name}` in this form."

    f = sess.filled[idx]
    parts = [
        f"**{f.get('name')}**  {_glyph(f.get('source', ''))} [{f.get('source')}",
    ]
    conf = f.get("confidence")
    if isinstance(conf, (int, float)):
        parts[0] += f" · conf={conf:.2f}"
    parts[0] += "]"
    if f.get("label"):
        parts.append(f"Label: {f['label']}")
    value = f.get("value")
    if isinstance(value, list):
        parts.append("Value (list):")
        for item in value:
            parts.append(f"  - {item}")
    else:
        parts.append("Value:")
        parts.append(str(value))
    return "\n".join(parts)


def format_next_missing(sess: Session) -> str:
    if not sess.missing_required:
        return "🎉 Nothing missing. Type `submit` to send."
    name = sess.missing_required[0]
    q_label = _missing_label(sess, name)
    options_hint = ""
    for q in sess.questions:
        for f in q.get("fields") or []:
            if f.get("name") == name:
                opts = f.get("values") or f.get("options") or []
                if isinstance(opts, list) and opts:
                    nice = []
                    for o in opts[:10]:
                        if isinstance(o, dict):
                            label = o.get("label") or o.get("value")
                            nice.append(str(label))
                        else:
                            nice.append(str(o))
                    options_hint = "\nOptions: " + " | ".join(nice)
                break
    return (
        f"Next required field: **{name}**\n"
        f"Question: {q_label or '(no label)'}{options_hint}\n"
        f"Reply with `answer {name} <your value>`."
    )


def format_submission_result(
    *, dry_run: bool, success: bool, error: str | None,
    application_id: str | None, status_code: int | None,
    fields_submitted: list[str] | None, missing_required: list[str] | None,
) -> str:
    if success and dry_run:
        return (
            "✓ **Dry-run complete.** Payload validated, nothing was posted.\n"
            f"Fields prepared: {len(fields_submitted or [])}.\n"
            "To send for real, reply `submit live`."
        )
    if success:
        line = f"✅ **Application submitted.** status={status_code}"
        if application_id:
            line += f"  application_id={application_id}"
        return line + f"\nFields submitted: {len(fields_submitted or [])}."
    msg = f"❌ Submission failed."
    if error:
        msg += f"\n{error}"
    if missing_required:
        labels = [str(m) for m in missing_required]
        msg += f"\nMissing required: {', '.join(labels)}"
    return msg

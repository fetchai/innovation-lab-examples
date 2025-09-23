"""
Markdown formatting helpers for consistent user output.
"""

import ast
from typing import Any, Dict, List
from datetime import datetime, timezone


def extract_gmail_response(intermediate_steps: List) -> Dict[str, Any]:
    email_id = "N/A"
    thread_id = "N/A"
    labels: List[str] = []
    try:
        if intermediate_steps:
            observation = intermediate_steps[-1][1]
            parsed = None
            if isinstance(observation, dict):
                parsed = observation
            elif isinstance(observation, str):
                brace_idx = observation.find("{")
                if brace_idx != -1:
                    dict_str = observation[brace_idx:]
                    try:
                        parsed = ast.literal_eval(dict_str)
                    except Exception:
                        parsed = None
            if parsed and isinstance(parsed, dict):
                resp = parsed.get('data', {}).get('response_data', {})
                email_id = resp.get('id', email_id)
                thread_id = resp.get('threadId', thread_id)
                labels = resp.get('labelIds', labels) or labels
    except Exception:
        pass
    return {"email_id": email_id, "thread_id": thread_id, "labels": labels}


def format_success_markdown(recipient: str, sender_email: str, subject: str, body: str, email_id: str, thread_id: str, labels: List[str]) -> str:
    return f"""✅ **Email sent successfully to {recipient}!**

**Email Details:**
- **From:** {sender_email}
- **Subject:** {subject}
- **Body:** {body}

**Gmail Response:**
- **Email ID:** `{email_id}`
- **Thread ID:** `{thread_id}`
- **Labels:** {', '.join(labels) if labels else 'N/A'}
- **Status:** ✅ Sent successfully"""


def format_reply_success_markdown(recipient: str, body: str, thread_id: str, message_id: str | None) -> str:
    return f"""✅ **Replied successfully**

**Reply Details:**
- **To:** {recipient}
- **Thread ID:** `{thread_id}`
- **Message ID:** `{message_id or 'N/A'}`
- **Body:** {body[:500]}{'...' if body and len(body) > 500 else ''}
"""


def format_trash_success_markdown(message_id: str, thread_id: str | None, labels: List[str] | None) -> str:
    return f"""🗑️ **Moved to Trash**

**Email:**
- **Message ID:** `{message_id}`
- **Thread ID:** `{thread_id or 'N/A'}`
- **Labels:** {', '.join(labels or []) if labels else 'TRASH'}
"""


def format_contacts_markdown(connections: List[Dict[str, Any]], next_page_token: str | None) -> str:
    lines = ["👥 **Contacts**\n"]
    for idx, c in enumerate(connections, start=1):
        names = []
        emails = []
        try:
            for n in c.get("names", []) or []:
                if n.get("displayName"):
                    names.append(n.get("displayName"))
            for e in c.get("emailAddresses", []) or []:
                if e.get("value"):
                    emails.append(e.get("value"))
        except Exception:
            pass
        lines.append(f"- {idx}. **Name:** {', '.join(names) if names else '(unknown)'}  - **Emails:** {', '.join(emails) if emails else '(none)'}")
    if next_page_token:
        lines.append("")
        lines.append(f"Next page token: `{next_page_token}`")
    return "\n".join(lines)


def format_people_search_markdown(results: List[Dict[str, Any]], next_page_token: str | None) -> str:
    lines = ["🔎 **People Search Results**\n"]
    for idx, p in enumerate(results, start=1):
        names = []
        emails = []
        phones = []
        try:
            for n in p.get("names", []) or []:
                if n.get("displayName"):
                    names.append(n.get("displayName"))
            for e in p.get("emailAddresses", []) or []:
                if e.get("value"):
                    emails.append(e.get("value"))
            for ph in p.get("phoneNumbers", []) or []:
                if ph.get("value"):
                    phones.append(ph.get("value"))
        except Exception:
            pass
        lines.append(
            f"- {idx}. **Name:** {', '.join(names) if names else '(unknown)'}  - **Emails:** {', '.join(emails) if emails else '(none)'}  - **Phones:** {', '.join(phones) if phones else '(none)'}"
        )
    if next_page_token:
        lines.append("")
        lines.append(f"Next page token: `{next_page_token}`")
    if not results:
        lines.append("No matches found. Try a different name or email.")
    return "\n".join(lines)


def _format_ts(ts_val: Any) -> str:
    try:
        if ts_val is None or ts_val == "":
            return "(no time)"
        # If already an ISO-like string, return as-is
        if isinstance(ts_val, str) and ("T" in ts_val or ts_val.isalpha() or ":" in ts_val):
            return ts_val
        # If numeric string (ms or s)
        if isinstance(ts_val, str) and ts_val.isdigit():
            n = int(ts_val)
            # Gmail internalDate is in ms
            if n > 10_000_000_000:
                n = n / 1000.0
            dt = datetime.fromtimestamp(n, tz=timezone.utc)
            return dt.strftime("%B %d, %Y, %I:%M %p UTC")
        if isinstance(ts_val, (int, float)):
            n = ts_val
            if n > 10_000_000_000:
                n = n / 1000.0
            dt = datetime.fromtimestamp(n, tz=timezone.utc)
            return dt.strftime("%B %d, %Y, %I:%M %p UTC")
    except Exception:
        pass
    return str(ts_val)


def format_thread_messages_markdown(messages: List[Dict[str, Any]], next_page_token: str | None) -> str:
    header = "🧵 **Thread Messages**\n"
    # Include thread header when available
    thread_id_hdr = None
    if messages:
        first = messages[0]
        thread_id_hdr = first.get("threadId") or first.get("thread_id")
    lines = [header]
    if thread_id_hdr:
        lines.append(f"Here are the details of the email thread with ID {thread_id_hdr}:\n")
    if not messages:
        lines.append("(no messages found)")
    for idx, m in enumerate(messages, start=1):
        subject = m.get("subject") or "(no subject)"
        sender = m.get("sender") or m.get("from") or "(unknown sender)"
        to_email = m.get("to") or m.get("recipient") or "(unknown recipient)"
        ts = _format_ts(m.get("messageTimestamp") or m.get("timestamp") or m.get("internalDate"))
        body_text = m.get("messageText") or ""
        if not body_text:
            preview_obj = m.get("preview") or {}
            if isinstance(preview_obj, dict):
                body_text = preview_obj.get("body") or ""
        message_id = m.get("messageId") or m.get("id") or ""
        labels = m.get("labelIds") or []
        lines.append(
            f"- {idx}. **From:** {sender}\n  - **To:** {to_email}\n  - **Subject:** {subject}\n  - **Time:** {ts}\n  - **Message ID:** `{message_id}`\n  - **Labels:** {', '.join(labels) if labels else 'N/A'}\n  - **Body:** {body_text[:500]}{'...' if body_text and len(body_text) > 500 else ''}"
        )
    if next_page_token:
        lines.append("")
        lines.append(f"Next page token: `{next_page_token}`")
    return "\n".join(lines)


def format_profile_markdown(profile: Dict[str, Any]) -> str:
    email = profile.get("emailAddress") or profile.get("email") or "(unknown)"
    messages_total = profile.get("messagesTotal", "?")
    threads_total = profile.get("threadsTotal", "?")
    history_id = profile.get("historyId", "?")
    return (
        "📇 **Profile**\n\n"
        f"- **Email:** {email}\n"
        f"- **Messages Total:** {messages_total}\n"
        f"- **Threads Total:** {threads_total}\n"
        f"- **History ID:** {history_id}"
    )


def format_drafts_list_markdown(drafts: List[Dict[str, Any]], next_page_token: str | None) -> str:
    lines = ["📝 **Drafts**\n"]
    for idx, d in enumerate(drafts, start=1):
        draft_id = d.get("id") or d.get("draftId") or ""
        subject = d.get("subject") or "(no subject)"
        to_email = d.get("to") or d.get("recipient") or "(unknown)"
        ts = d.get("messageTimestamp") or ""
        lines.append(
            f"- {idx}. **Draft ID:** `{draft_id}`  - **To:** {to_email}  - **Subject:** {subject}  - **Time:** {ts}"
        )
    if next_page_token:
        lines.append("")
        lines.append(f"Next page token: `{next_page_token}`")
    if not drafts:
        lines.append("(no drafts)")
    return "\n".join(lines)


def format_single_message_markdown(message: Dict[str, Any]) -> str:
    subject = message.get("subject") or "(no subject)"
    sender = message.get("sender") or "(unknown sender)"
    to = message.get("to") or "(unknown recipient)"
    ts = message.get("messageTimestamp") or "(no time)"
    body_text = message.get("messageText") or ""
    if not body_text:
        preview_obj = message.get("preview") or {}
        if isinstance(preview_obj, dict):
            body_text = preview_obj.get("body") or ""
    message_id = message.get("messageId") or ""
    thread_id = message.get("threadId") or ""
    labels = message.get("labelIds") or []
    return (
        "✉️ **Email Message**\n\n"
        f"- **Subject:** {subject}\n"
        f"- **From:** {sender}\n"
        f"- **To:** {to}\n"
        f"- **Time:** {ts}\n"
        f"- **Message ID:** `{message_id}`\n"
        f"- **Thread ID:** `{thread_id}`\n"
        f"- **Labels:** {', '.join(labels) if labels else 'N/A'}\n"
        f"- **Body:** {body_text[:1000]}{'...' if body_text and len(body_text) > 1000 else ''}"
    )


def format_draft_created_markdown(draft_id: str, thread_id: str | None, to_email: str, subject: str) -> str:
    return f"""📝 **Draft created**

**Draft Details:**
- **Draft ID:** `{draft_id}`
- **Thread ID:** `{thread_id or 'N/A'}`
- **To:** {to_email}
- **Subject:** {subject}
"""


def format_draft_sent_markdown(draft_id: str) -> str:
    return f"""📤 **Draft sent**

- **Draft ID:** `{draft_id}`
"""


def format_draft_deleted_markdown(draft_id: str) -> str:
    return f"""🗑️ **Draft deleted**

- **Draft ID:** `{draft_id}`
"""


def format_fetched_emails_markdown(messages: List[Dict[str, Any]], next_page_token: str | None, estimate: int) -> str:
    lines = ["📥 **Fetched Emails (latest)**\n"]
    for idx, m in enumerate(messages, start=1):
        subject = m.get("subject") or "(no subject)"
        sender = m.get("sender") or "(unknown sender)"
        to = m.get("to") or "(unknown recipient)"
        ts = m.get("messageTimestamp") or "(no time)"
        # Prefer full message text when available; fallback to preview.body
        body_text = m.get("messageText") or ""
        if not body_text:
            preview_obj = m.get("preview") or {}
            if isinstance(preview_obj, dict):
                body_text = preview_obj.get("body") or ""
        message_id = m.get("messageId") or ""
        thread_id = m.get("threadId") or ""
        labels = m.get("labelIds") or []
        lines.append(
            f"- {idx}. **Subject:** {subject}\n  - **From:** {sender}\n  - **To:** {to}\n  - **Time:** {ts}\n  - **Message ID:** `{message_id}`\n  - **Thread ID:** `{thread_id}`\n  - **Labels:** {', '.join(labels) if labels else 'N/A'}\n  - **Body:** {body_text[:500]}{'...' if body_text and len(body_text) > 500 else ''}"
        )
    lines.append("")
    lines.append(f"Estimated total: {estimate}")
    if next_page_token:
        lines.append(f"Next page token: `{next_page_token}`")
    return "\n".join(lines)



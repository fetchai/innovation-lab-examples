"""Small shared helpers (kept minimal to avoid circular imports)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from uagents_core.contrib.protocols.chat import (
    AgentContent,
    ChatMessage,
    EndSessionContent,
    TextContent,
)


def create_text_chat(text: str, *, end_session: bool = False) -> ChatMessage:
    """Build a simple text-only ChatMessage (optionally closing the session)."""
    content: list[AgentContent] = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )


_ARTICLE_ID_PROSE_RE = re.compile(
    r"article[_\s-]?id[\s:=\"']*([A-Za-z0-9_\-]+)", re.IGNORECASE
)
_BACK_TO_NEWS_RE = re.compile(r"back[_\s-]?to[_\s-]?news", re.IGNORECASE)


def parse_card_selection(text: str) -> dict[str, str] | None:
    """Extract a card-selection dict from inbound text.

    The chat UI delivers selections in one of two shapes:

    - Direct @mention: a JSON object serialized as text, e.g.
      `{"article_id": "hn_42", "source": "news_tab"}`.
    - Via the planner: free prose mentioning the selection fields, e.g.
      `"The user picked article_id hn_42 from news_tab."`.

    Returns a dict with at least one of `article_id` or `action` keys, or
    `None` if the text doesn't look like a card selection.
    """
    if not text:
        return None

    stripped = text.strip()

    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            result: dict[str, str] = {}
            for key in ("article_id", "action", "source"):
                value = data.get(key)
                if isinstance(value, str):
                    result[key] = value
            if result:
                return result

    selection: dict[str, str] = {}
    if _BACK_TO_NEWS_RE.search(stripped):
        selection["action"] = "back_to_news"

    match = _ARTICLE_ID_PROSE_RE.search(stripped)
    if match:
        selection["article_id"] = match.group(1)

    return selection or None

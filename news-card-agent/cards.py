"""Card builders using Agentverse element-tree primitives.

Two card kinds are produced:

1. News list card - a `section` containing a `list` of news items. Each item
   has an image, a title/description group, and a "Read Full Article" button
   whose `action.selection` carries the `article_id`.
2. Article detail card - rendered when the user taps "Read Full Article".

The agent sends each card as a `MetadataContent` block on the chat protocol,
following:
https://docs.agentverse.ai/documentation/advanced-usages/agent-driven-interactive-cards
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    MetadataContent,
    TextContent,
)

from news_client import Article


CARD_PROTOCOL_VERSION = "1"
NEWS_TAB_SOURCE = "news_tab"


def build_news_list_payload(
    articles: list[Article],
    *,
    title: str = "Latest News",
    subtitle: str | None = "Tap an article to read more",
    summaries: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the `card_payload` dict for the news list card.

    `summaries` optionally overrides each article's subtitle text (keyed by
    `article_id`); defaults to the article's raw description.
    """
    summaries = summaries or {}
    items: list[dict[str, Any]] = []

    for article in articles:
        subtitle_text = summaries.get(article.article_id) or article.description
        items.append(
            {
                "children": [
                    {
                        "type": "image",
                        "src": article.image_url,
                        "alt": f"Image for {article.title}",
                        "aspect_ratio": "16:9",
                    },
                    {
                        "type": "group",
                        "direction": "column",
                        "gap": 8,
                        "children": [
                            {
                                "type": "heading",
                                "value": article.title,
                                "level": 3,
                            },
                            {
                                "type": "text",
                                "value": subtitle_text,
                                "style": "body",
                            },
                            {
                                "type": "badge",
                                "label": article.source,
                                "variant": "info",
                            },
                        ],
                    },
                    {
                        "type": "button",
                        "label": "Read Full Article",
                        "primary": True,
                        "action": {
                            "selection": {
                                "article_id": article.article_id,
                                "source": NEWS_TAB_SOURCE,
                            }
                        },
                    },
                ]
            }
        )

    section: dict[str, Any] = {
        "type": "section",
        "title": title,
        "children": [
            {
                "type": "list",
                "items": items,
            }
        ],
    }
    if subtitle:
        section["subtitle"] = subtitle

    return {"root": section}


def build_article_detail_payload(article: Article) -> dict[str, Any]:
    """Build the `card_payload` dict for the article detail card."""
    section: dict[str, Any] = {
        "type": "section",
        "title": article.title,
        "children": [
            {
                "type": "image",
                "src": article.image_url,
                "alt": f"Hero image for {article.title}",
                "aspect_ratio": "16:9",
            },
            {
                "type": "group",
                "direction": "column",
                "gap": 12,
                "children": [
                    {
                        "type": "badge",
                        "label": article.source,
                        "variant": "info",
                    },
                    {
                        "type": "heading",
                        "value": article.title,
                        "level": 2,
                    },
                    {
                        "type": "text",
                        "value": article.description or "Tap the source link below to read the full article.",
                        "style": "body",
                    },
                    {"type": "divider"},
                    {
                        "type": "text",
                        "value": f"Source: {article.url}",
                        "style": "muted",
                    },
                ],
            },
            {
                "type": "group",
                "direction": "row",
                "gap": 8,
                "children": [
                    {
                        "type": "button",
                        "label": "Back to News",
                        "primary": False,
                        "action": {
                            "selection": {
                                "action": "back_to_news",
                                "source": NEWS_TAB_SOURCE,
                            }
                        },
                    },
                ],
            },
        ],
    }
    return {"root": section}


def _card_metadata(card_payload: dict[str, Any]) -> MetadataContent:
    """Wrap a payload dict into a MetadataContent block for ChatMessage."""
    return MetadataContent(
        type="metadata",
        metadata={
            "card_protocol_version": CARD_PROTOCOL_VERSION,
            "requires_card_interaction": "true",
            "card_kind": "custom",
            "card_payload": json.dumps(card_payload),
        },
    )


def build_news_list_message(
    *,
    preamble: str,
    articles: list[Article],
    summaries: dict[str, str] | None = None,
    title: str = "Latest News",
) -> ChatMessage:
    """Create a ChatMessage carrying the news list card + an intro text bubble."""
    payload = build_news_list_payload(articles, title=title, summaries=summaries)
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=preamble),
            _card_metadata(payload),
        ],
    )


def build_article_detail_message(
    *,
    preamble: str,
    article: Article,
) -> ChatMessage:
    """Create a ChatMessage carrying the article detail card.

    The article URL is also included as a markdown link inside the text bubble
    so that users can open the source in a new tab directly from chat.
    """
    payload = build_article_detail_payload(article)
    text = f"{preamble}\n\n[Open original article]({article.url})"
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=text),
            _card_metadata(payload),
        ],
    )

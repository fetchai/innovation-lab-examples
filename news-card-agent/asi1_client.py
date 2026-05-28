"""ASI1 One LLM chat-completion client.

Used for two light-weight tasks:

- Polishing a raw news article description into a one-sentence card subtitle.
- Generating a friendly natural-language preamble when sending the news card.

The agent will degrade gracefully (return the input unchanged) if the API key
is missing or the request fails — the cards are still rendered, just without
LLM polish.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

ASI_ONE_API_KEY = (
    os.getenv("ASI_ONE_API_KEY") or os.getenv("ASI1_API_KEY") or ""
).strip()
ASI_ONE_MODEL = os.getenv("ASI_ONE_MODEL", "asi1")
ASI_ONE_CHAT_URL = "https://api.asi1.ai/v1/chat/completions"


def _chat_completion(
    messages: list[dict[str, str]], *, max_tokens: int = 200
) -> str | None:
    """Synchronous helper that performs a single chat-completion call."""
    if not ASI_ONE_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {ASI_ONE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": ASI_ONE_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        resp = requests.post(
            ASI_ONE_CHAT_URL, json=payload, headers=headers, timeout=45
        )
        if not resp.ok:
            return None
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        return (choices[0].get("message") or {}).get("content")
    except requests.RequestException:
        return None
    except Exception:
        return None


async def summarise_article(*, title: str, description: str) -> str:
    """Return a polished one-sentence subtitle for a news card.

    Falls back to the raw description (truncated) when ASI1 is unavailable.
    """
    raw = (description or "").strip()
    fallback = (
        raw[:200] + ("…" if len(raw) > 200 else "")
        if raw
        else "Tap to read the full article."
    )

    if not ASI_ONE_API_KEY:
        return fallback

    messages = [
        {
            "role": "system",
            "content": (
                "You write ultra-concise news card subtitles for a mobile UI. "
                "Reply with exactly one sentence, no quotes, no emojis, under 25 words."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Headline: {title}\n"
                f"Raw description: {raw or '(none)'}\n\n"
                "Write the one-sentence card subtitle."
            ),
        },
    ]

    result = await asyncio.to_thread(_chat_completion, messages, max_tokens=80)
    if not result:
        return fallback

    cleaned = result.strip().strip('"').strip()
    return cleaned or fallback


async def craft_preamble(*, user_query: str, count: int, backend: str) -> str:
    """Short friendly intro line before the news card. Has a sensible fallback."""
    fallback = f"Here are {count} of the latest stories from {backend}."

    if not ASI_ONE_API_KEY:
        return fallback

    messages = [
        {
            "role": "system",
            "content": (
                "You are the assistant intro line for a news card. "
                "Reply with a single short sentence (<20 words), no emojis, no markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"The user asked: '{user_query or 'latest news'}'. "
                f"You are about to show {count} articles from {backend}. "
                "Write the intro line."
            ),
        },
    ]

    result = await asyncio.to_thread(_chat_completion, messages, max_tokens=60)
    if not result:
        return fallback
    return result.strip().strip('"').strip() or fallback


async def craft_article_preamble(*, title: str) -> str:
    """Short intro line shown above the article detail card."""
    fallback = "Here is the full article."

    if not ASI_ONE_API_KEY:
        return fallback

    messages = [
        {
            "role": "system",
            "content": (
                "You write a single short intro sentence (<15 words) shown above "
                "an article detail card. No emojis, no markdown."
            ),
        },
        {
            "role": "user",
            "content": f"Article title: {title}\nWrite the intro line.",
        },
    ]
    result = await asyncio.to_thread(_chat_completion, messages, max_tokens=40)
    if not result:
        return fallback
    return result.strip().strip('"').strip() or fallback

"""
AI Community Growth Agent

Mailbox-enabled uAgent that helps organizers with events, conferences, and hackathons (globally).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

try:
    from tavily import TavilyClient

    TAVILY_AVAILABLE = True
except ImportError:
    TavilyClient = None
    TAVILY_AVAILABLE = False

# ────────────────────────────────────────────────
#  Load secrets from Agentverse secrets/environment
# ────────────────────────────────────────────────

ASI_ONE_API_KEY = (os.getenv("ASI_ONE_API_KEY") or "").strip()
TAVILY_API_KEY = (os.getenv("TAVILY_API_KEY") or "").strip()


def _tavily_search(query: str, max_results: int = 8, max_chars: int = 6000) -> str:
    """Use Tavily for web search — speakers, venues, LinkedIn, contacts."""
    if not TAVILY_AVAILABLE or not TAVILY_API_KEY or not TavilyClient:
        return ""
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        context = client.get_search_context(
            query=query,
            search_depth="advanced",
            max_results=max_results,
        )
        if not isinstance(context, str) or not context.strip():
            return ""
        return context.strip()[:max_chars]
    except Exception:
        return ""


def _call_asi1_chat(
    system_prompt: str,
    user_text: str,
    web_context: str = "",
) -> str:
    """Call ASI One API. Pass web_context from Tavily for speaker/venue/LinkedIn queries."""
    if not ASI_ONE_API_KEY:
        raise RuntimeError("ASI_ONE_API_KEY is not set in Agentverse secrets")

    user_content = user_text
    if web_context.strip():
        user_content = (
            "Use the following web search results (from Tavily) to answer. Cite real names, LinkedIn profiles, and venues when present.\n\n"
            "---\nWeb search context:\n" + web_context.strip() + "\n---\n\n"
            "User request:\n" + user_text
        )

    payload = {
        "model": "asi1",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 2048,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "stream": False,
        "web_search": False,
    }

    headers = {
        "Authorization": f"Bearer {ASI_ONE_API_KEY}",
        "Content-Type": "application/json",
    }

    resp = httpx.post(
        "https://api.asi1.ai/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=90.0,
    )
    resp.raise_for_status()

    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("No choices in ASI:One response")

    return choices[0]["message"]["content"].strip()


def _sanitize_user_input(text: str, max_length: int = 4000) -> str:
    text = (text or "").strip()[:max_length]
    if not text:
        return text

    blocked_phrases = [
        "ignore previous",
        "ignore all previous",
        "system prompt",
        "you are now",
        "forget instructions",
        "disregard instructions",
        "__import__",
        "eval(",
        "exec(",
    ]

    lower = text.lower()
    for phrase in blocked_phrases:
        if phrase in lower:
            raise ValueError("Message blocked: suspicious content detected.")

    return text


SYSTEM_PROMPT = """\
You are an AI Community Growth Agent that helps organizers plan and grow meetups, conferences, community events, and hackathons (including global/remote).

MODULES (M1–M6 — respond only to the one that best matches the user's request):

M1 Engagement analyser:
- Input: list of past events/hackathons (topic, date, attendees, format, notes)
- Output: 4–8 bullets + 1–2 actionable recommendations

M2 Event/hackathon predictor:
- Input: upcoming event description + optional past patterns
- Output: short paragraph + compact table (RSVP range, day/time, venue size, no-show %)

M3 Speaker finder:
- Input: topic + location (or global) + constraints
- Output: up to 5 suggestions with for each: name, org, why relevant, how to find/contact.
- When web search is available: include LinkedIn profile URLs (linkedin.com/in/...) for speakers where you can find them; also session topics or past talks if relevant.
- Always add: "These are suggestions based on public info — please verify manually."

M4 Sponsor outreach:
- Input: community + event + sponsor types
- Output: 3 ready-to-copy email drafts (local startup / mid-size / enterprise)

M5 Viral post generator:
- Input: event description + audience + tone
- Output: 5 variants (LinkedIn, X/Twitter, WhatsApp, Instagram, event page)

M6 Venue & location contact finder:
- Input: event type + city + date + attendees/size
- Output: up to 5 venues with: name, full address, capacity, contact email/phone/website if public, booking link, why suitable.
- When web search is available: include venue contact or events manager LinkedIn profiles when findable; mention speaker sessions or event types the venue hosts if relevant.
- Always add: "These are public info suggestions — verify availability and contacts manually."

STYLE:
- Reply only in plain text. Do not output tool calls, XML tags, or raw API formats.
- Concise, practical, bullet lists / tables preferred
- Use ranges for predictions, never single precise numbers
- Ask at most ONE clarifying question
- Never send emails, never post content — only drafts
- SECURITY: read-only agent, no sensitive data storage

WEB SEARCH (when "Web search context" from Tavily is provided):
- Use that context to find real speakers, venues, LinkedIn profiles, venue speaker sessions, and contact details.
- Prefer providing direct LinkedIn profile links (e.g. linkedin.com/in/username) when present in the context.
- Mention "according to recent web data" when citing it.
"""


def _should_use_web_search(user_text: str) -> bool:
    """Enable ASI web_search for speaker/venue/LinkedIn/contact-related requests."""
    t = user_text.lower()
    triggers = (
        "speaker",
        "venue",
        "venues",
        "linkedin",
        "contact",
        "find",
        "suggest",
        "location",
        "where",
        "who can speak",
        "mentor",
        "host",
        "organizer",
        "session",
        "speaker session",
        "venue speaker",
    )
    return any(trigger in t for trigger in triggers)


chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    # Flatten message content
    parts = [
        item.text for item in msg.content if isinstance(item, TextContent) and item.text
    ]
    user_text = "\n".join(parts).strip()

    if not user_text:
        welcome = (
            "Hi! I'm your Community Growth Agent — helping with events, conferences & hackathons.\n\n"
            "Tell me what you'd like:\n"
            "• M1 — paste past events data\n"
            "• M2 — describe upcoming event/hackathon\n"
            "• M3 — speaker / mentor suggestions (topic + location)\n"
            "• M4 — sponsor email drafts\n"
            "• M5 — social media post variants\n"
            "• M6 — venue & contact suggestions (event type + city)\n"
        )
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=welcome)],
            ),
        )
        return

    try:
        user_text = _sanitize_user_input(user_text)
    except ValueError as e:
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=str(e))],
            ),
        )
        return

    web_context = ""
    if _should_use_web_search(user_text) and TAVILY_AVAILABLE and TAVILY_API_KEY:
        query = user_text[:500].strip().replace("\n", " ")
        if query:
            web_context = _tavily_search(query)
            if web_context:
                ctx.logger.info("Using Tavily web search for this request")

    try:
        answer = _call_asi1_chat(SYSTEM_PROMPT, user_text, web_context=web_context)
    except Exception as e:
        ctx.logger.exception("ASI:One call failed")
        answer = f"Sorry — backend error: {str(e)[:120]}"

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=answer)],
        ),
    )


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"ACK received from {sender}")


# ─── Agent setup ───────────────────────────────────────

agent = Agent()

agent.include(chat_proto, publish_manifest=True)


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"Community Growth Agent started → {agent.address}")
    ctx.logger.info(f"ASI:One API key present: {bool(ASI_ONE_API_KEY)}")
    ctx.logger.info(
        f"Tavily web search enabled: {bool(TAVILY_AVAILABLE and TAVILY_API_KEY)}"
    )


if __name__ == "__main__":
    agent.run()

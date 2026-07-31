"""
News Summarizer Agent

A beginner-friendly Fetch.ai uAgent that fetches the latest news headlines
for a topic using NewsAPI and summarizes them with the ASI:One LLM.
Supports the Chat Protocol so it can be used directly from ASI:One
or any other Agentverse-connected agent.
"""

import os
from datetime import datetime, timezone
from uuid import uuid4

import requests
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

load_dotenv()

ASI1_API_KEY = os.getenv("ASI1_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

NEWS_API_URL = "https://newsapi.org/v2/everything"
ASI1_API_URL = "https://api.asi1.ai/v1/chat/completions"


def fetch_headlines(topic: str) -> list[str]:
    """Fetch the top 5 news headlines for a given topic using NewsAPI."""
    params = {
        "q": topic,
        "pageSize": 5,
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": NEWS_API_KEY,
    }
    response = requests.get(NEWS_API_URL, params=params, timeout=15)
    response.raise_for_status()
    articles = response.json().get("articles", [])
    return [a["title"] for a in articles if a.get("title")]


def summarize_with_asi1(topic: str, headlines: list[str]) -> str:
    """Send headlines to the ASI:One LLM and return a readable summary."""
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    prompt = (
        f"Here are the top {len(headlines)} recent news headlines about "
        f"'{topic}':\n\n{headlines_text}\n\n"
        f"Please write a short, clear, 3-4 sentence summary of what is "
        f"currently happening with '{topic}' based on these headlines."
    )

    headers = {
        "Authorization": f"Bearer {ASI1_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "asi1-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 300,
        "stream": False,
    }

    response = requests.post(ASI1_API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return str(data["choices"][0]["message"]["content"])


def build_news_summary(topic: str) -> str:
    """Fetch headlines for a topic and return a formatted summary string."""
    topic = topic.strip()
    if not topic:
        return "Please tell me a topic to summarize, e.g. 'AI', 'climate', or 'sports'."

    if not NEWS_API_KEY:
        return (
            "This agent is missing a NEWS_API_KEY — ask the operator to configure it."
        )
    if not ASI1_API_KEY:
        return (
            "This agent is missing an ASI1_API_KEY — ask the operator to configure it."
        )

    headlines = fetch_headlines(topic)
    if not headlines:
        return f"No recent headlines found for '{topic}'. Try a different topic."

    summary = summarize_with_asi1(topic, headlines)
    headlines_block = "\n".join(f"- {h}" for h in headlines)
    return f"Top headlines for '{topic}':\n{headlines_block}\n\nSummary:\n{summary}"


def run_cli(topic: str) -> None:
    """Run the agent's summary flow once and print the result (for local testing)."""
    print(f"\nFetching top headlines for topic: '{topic}'...")
    print(build_news_summary(topic))


# ─── Chat Protocol ──────────────────────────────────────────────

chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    topic = "\n".join(
        item.text for item in msg.content if isinstance(item, TextContent) and item.text
    ).strip()

    if not topic:
        reply = (
            "Hi! Send me a topic (e.g. 'AI', 'climate', or 'sports') and "
            "I'll fetch the latest headlines and summarize them for you."
        )
    else:
        try:
            reply = build_news_summary(topic)
        except requests.RequestException as exc:
            ctx.logger.exception("Upstream API request failed")
            reply = f"Sorry, I couldn't fetch news for '{topic}' right now ({exc})."

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=reply)],
        ),
    )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info(
        f"Received acknowledgement from {sender} for message {msg.acknowledged_msg_id}"
    )


# ─── Agent setup ─────────────────────────────────────────────────

agent = Agent()

agent.include(chat_proto, publish_manifest=True)


@agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info(f"News Summarizer Agent started at address {agent.address}")
    ctx.logger.info(f"NEWS_API_KEY configured: {bool(NEWS_API_KEY)}")
    ctx.logger.info(f"ASI1_API_KEY configured: {bool(ASI1_API_KEY)}")


if __name__ == "__main__":
    agent.run()

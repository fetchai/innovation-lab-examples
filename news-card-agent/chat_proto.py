"""Chat protocol handlers for the news-card agent.

Flow:

1. User sends any text (e.g. "show me tech news") → the agent fetches news,
   caches each article in storage by `article_id`, polishes subtitles with
   ASI1, and replies with a `custom` card containing a list of articles plus
   "Read Full Article" buttons.

2. User taps a button → the chat UI forwards a follow-up `ChatMessage` whose
   `TextContent` is the selection (JSON for direct @mention, prose via the
   planner). We parse it, look the article up in storage, and reply with a
   new article detail card.

3. The detail card also has a "Back to News" button which re-runs step 1.

There is intentionally no payment protocol on this agent.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    MetadataContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from asi1_client import (
    craft_article_preamble,
    craft_preamble,
    summarise_article,
)
from cards import (
    build_article_detail_message,
    build_news_list_message,
)
from news_client import Article, active_backend, fetch_news
from shared import create_text_chat, parse_card_selection


chat_proto = Protocol(spec=chat_protocol_spec)


LAST_QUERY_KEY = "news:last_query"
ARTICLE_KEY_PREFIX = "news:article:"


def _store_articles(ctx: Context, articles: list[Article]) -> None:
    """Persist articles in storage so we can look them up on card click."""
    for article in articles:
        ctx.storage.set(ARTICLE_KEY_PREFIX + article.article_id, json.dumps(article.to_dict()))


def _load_article(ctx: Context, article_id: str) -> Article | None:
    raw = ctx.storage.get(ARTICLE_KEY_PREFIX + article_id)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    try:
        return Article.from_dict(data)
    except TypeError:
        return None


async def _send_news_card(ctx: Context, sender: str, query: str) -> None:
    """Fetch news, polish, store, and send the news list card."""
    ctx.logger.info(f"Fetching news for query='{query}' via {active_backend()}")
    try:
        articles = await fetch_news(query=query)
    except Exception as exc:
        ctx.logger.exception("News fetch failed")
        await ctx.send(sender, create_text_chat(f"Sorry, I couldn't fetch the news right now: {exc}"))
        return

    if not articles:
        await ctx.send(sender, create_text_chat("No news articles found. Try a different topic?"))
        return

    _store_articles(ctx, articles)
    ctx.storage.set(LAST_QUERY_KEY, query)

    # Summarise + craft preamble concurrently.
    preamble_task = craft_preamble(
        user_query=query, count=len(articles), backend=active_backend()
    )
    summary_tasks = [
        summarise_article(title=a.title, description=a.description) for a in articles
    ]
    preamble, *summaries_list = await asyncio.gather(preamble_task, *summary_tasks)

    summaries = {
        article.article_id: summary for article, summary in zip(articles, summaries_list)
    }

    message = build_news_list_message(
        preamble=preamble,
        articles=articles,
        summaries=summaries,
        title="Latest News" if not query or query.lower() in {"latest", "news"} else f"News · {query.title()}",
    )
    await ctx.send(sender, message)
    ctx.logger.info(f"Sent news card with {len(articles)} articles to {sender}")


async def _send_article_detail(ctx: Context, sender: str, article_id: str) -> None:
    """Look up an article and send the detail card."""
    article = _load_article(ctx, article_id)
    if not article:
        ctx.logger.warning(f"Article {article_id} not found in storage")
        await ctx.send(
            sender,
            create_text_chat(
                "I couldn't find that article anymore. Ask me for the latest news again."
            ),
        )
        return

    preamble = await craft_article_preamble(title=article.title)
    message = build_article_detail_message(preamble=preamble, article=article)
    await ctx.send(sender, message)
    ctx.logger.info(f"Sent detail card for article {article_id} to {sender}")


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Got a message from {sender}")

    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    # Greet on session start with a hint, and let the UI know we expect a query.
    if any(isinstance(c, StartSessionContent) for c in msg.content):
        await ctx.send(
            sender,
            create_text_chat(
                "Hi! Ask me for the latest news (try 'latest tech news', "
                "'world news', or just 'news')."
            ),
        )
        return

    for item in msg.content:
        if isinstance(item, TextContent):
            text = (item.text or "").strip()
            if not text:
                continue

            selection = parse_card_selection(text)
            if selection:
                ctx.logger.info(f"Parsed card selection: {selection}")
                if selection.get("action") == "back_to_news":
                    previous_query = ctx.storage.get(LAST_QUERY_KEY) or "latest"
                    await _send_news_card(ctx, sender, previous_query)
                    return
                article_id = selection.get("article_id")
                if article_id:
                    await _send_article_detail(ctx, sender, article_id)
                    return

            await _send_news_card(ctx, sender, text)
            return

        if isinstance(item, MetadataContent):
            ctx.logger.debug(f"Received metadata: {item.metadata}")


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}"
    )

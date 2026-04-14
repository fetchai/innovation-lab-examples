import os
import json
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from uagents import Context, Protocol
from openai import AsyncOpenAI
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from mcp_client import execute_mcp_tools

# Ensure .env is loaded before reading any env vars
# (guards against import-before-load_dotenv ordering issues)
load_dotenv()

# Initialize the ASI1-compatible LLM client once at module load
_openai_client = AsyncOpenAI(
    api_key=os.getenv("ASI1_API_KEY"),
    base_url="https://api.asi1.ai/v1",
)

# Protocol instance that adheres to the ASI1 chat specification
chat_proto = Protocol(spec=chat_protocol_spec)

# ──────────────────────────────────────────────────────────────────────────────
# System prompt — Slot-Filling + Consultancy reasoning:
#
#   Consultant Mode: Undecided users get 3 distinct "vibes" or destinations.
#   Slot-Filling Mode: Once a destination is picked, extract specifics.
#   Searcher Mode: Execute MCP tools only when Minimum Viable Context is met.
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are TicketLens Concierge, a high-end travel assistant for discovering global experiences.

## Your Mission
Guide users from initial browsing ("I'm bored") to specific tour results ("Skip-the-line Eiffel Tower tickets").

## Dual-Mode Protocol
1. **Consultancy Mode (Undecided)**:
   - If the user has no destination or is vague, act as a travel consultant.
   - Propose 3 distinct travel "vibes" or destinations from your own knowledge (e.g., Cultural Paris, Active Berlin, Relaxing Bali).
   - Ask: "Which of these vibes sounds like your perfect getaway, or should we look elsewhere?"
   - **Do not use MCP search tools in this mode.**

2. **Selection & Promotion**:
   - If the user picks one of your suggestions (e.g., "Paris sounds great"), "promote" it to your Active Search Context.
   - Transition immediately to Slot-Filling.

3. **Slot-Filling Mode (Decided)**:
   - Once a destination is identified, extract these features:
     - **Location** (Mandatory): City or Landmark name.
     - **Category/Vibe**: (e.g. History, Food, Nightlife, Adventure).
     - **Date Range / Timing**: (e.g. Next weekend, Summer).
     - **Budget / Group Size**: (Optional but helpful).
   - Rules: Collect these progressively. Do not ask for everything in one list.

4. **Searcher Mode (Execution)**:
   - **Never call search_tours without a confirmed Location.**
    - Landmark resolving: If a user specifies a landmark (e.g. "Big Ben"), always call **search_pois** first to get a POI ID, then use that ID in **search_tours**.
    - **Ambiguity Rule**: If search_pois returns multiple high-relevance matches in different cities (e.g. Colosseum in Rome vs El Jem), DO NOT pick one. Instead, ask the user: "I found multiple [Landmark]—did you mean the one in [City A] or [City B]?"

## Tool Payload Reference (Strict Schema)
All tools require arguments wrapped in a `payload` key. You MUST follow these exact keys; never use aliases like `q`, `id`, or `limit`.

**IMPORTANT**: After receiving tool results, you MUST summarize them for the user. Do NOT call the same tool again unless the user asks for more results.

### search_pois (Step 1 of Resolve)
- `payload: { query, city (optional), country (optional), language (optional) }`
- **Use for**: Resolving landmarks (e.g. "Eiffel Tower") to a POI ID.

### search_tours (Step 2 of Resolve or City Search)
- `payload: { query, poi: {id, match_mode: "exact"|"fuzzy"}, dates: {from_date, to_date} }`
- **Crucial**: Use `query` (NOT `q`).
- **FORBIDDEN fields** (will cause API errors): `city`, `per_page`, `limit`, `country`. Never use them.
- `poi` is an object: `{ "id": "123", "match_mode": "exact" }`.
- To filter by city, include the city name in the `query` string, e.g. `"query": "tours in Dubai"`.

### get_tour (Detail View)
- `payload: { tour_id, language }`
- **Crucial**: Use `tour_id` (NOT `id`).
- Call this when the user picks a specific result by number or name.

## Interaction Guidelines
- **Stay grounded**: Only use MCP tools for live search results. Never hallucinate prices or specific tours.
- **Tone**: Professional, insightful, and proactive.
- **Presentation**: When tool results are returned, I will inject available `image_url` values as a reference map. Embed images INLINE within your categorical response using standard Markdown: `![Experience Name](image_url)`. Place the image directly below the experience name inside its category section. Do NOT create a separate 'Discovered Experiences' section — images should appear inside your own structured response. 
- **Follow-up**: When a user selects a number, Attribute, or Title—call **get_tour**.
"""


def _build_send_response(text: str, end_session: bool = False):
    """Helper to build a ChatMessage response aligned with ASI1 standards."""
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """
    Handles incoming user messages via the official ASI1 Chat Protocol.

    Maintains full session context per sender across multiple turns.
    Runs the ASI1 LLM reasoning loop, executing MCP tool calls as needed,
    until a final text response is ready to return.
    """
    # 1. Acknowledge receipt immediately (required by the Chat Protocol)
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id
        ),
    )

    # 2. Extract plain text from the incoming content list
    #    Also identify session signals
    user_input = ""
    is_start_session = False
    for item in msg.content:
        if isinstance(item, TextContent):
            user_input += item.text
        elif isinstance(item, StartSessionContent):
            is_start_session = True

    # If it's ONLY a session start with no text, we just log it and wait for the first prompt
    if is_start_session and not user_input:
        ctx.logger.info(f"[{sender[:16]}...] Session started.")
        return

    # 2.1 Quota Management (Idea 4)
    # Track 100 network requests per day (UTC)
    today = datetime.now(timezone.utc).date().isoformat()
    quota_key = f"quota_{today}"
    current_usage = ctx.storage.get(quota_key) or 0
    is_offline_mode = current_usage >= 100

    # 3. Load or initialise the per-sender conversation history
    #    ctx.storage keys are strings; use sender address as the session key
    history_key = f"history_{sender}"
    session_data = ctx.storage.get(history_key)

    import time

    current_time = time.time()

    if session_data:
        # Compatibility/Migration: If it's still a plain list, migrate it
        if isinstance(session_data, list):
            messages = session_data
            last_active = current_time
        else:
            messages = session_data.get("messages", [])
            last_active = session_data.get("last_active", current_time)

        # Part 2: Session Stale Detection (2h = 7200s)
        if current_time - last_active > 7200:
            ctx.logger.info(
                f"[{sender[:16]}...] Session stale (>2h). Resetting context."
            )
            conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        else:
            conversation_history = messages
    else:
        conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Part 2: History Truncation (Limit to last 15 messages, preserving system prompt)
    if len(conversation_history) > 15:
        # Keep the system prompt at index 0, then the last 14 messages
        conversation_history = [conversation_history[0]] + conversation_history[-14:]

    # Append the new user message to history
    conversation_history.append({"role": "user", "content": user_input})

    # Retrieve pre-cached tool definitions from startup bootstrap.
    # If bootstrap failed (empty list), try once more — the MCP server may have recovered.
    tools_metadata = ctx.storage.get("tools_metadata") or []
    if not tools_metadata:
        ctx.logger.info("No tools cached — attempting lazy MCP bootstrap...")
        try:
            from mcp_client import fetch_mcp_tools

            tools_metadata = await fetch_mcp_tools(retries=2, backoff=1.0)
            ctx.storage.set("tools_metadata", tools_metadata)
            ctx.logger.info(
                f"Lazy bootstrap succeeded. {len(tools_metadata)} tool(s) loaded."
            )
        except BaseException as e:
            ctx.logger.warning(
                f"Lazy bootstrap also failed: {e}. Responding without tools."
            )

    # 4. ASI1 Reasoning Loop — continues while the model requests tool calls
    iteration = 0
    try:
        # Prepare messages for the LLM — we'll inject a hint if we detect a recovery
        llm_messages = list(conversation_history)

        # If the model previously apologized for a failure, but we now have tools,
        # add a hint to 'nudge' it back into searching mode without forcing it.
        if tools_metadata and any(
            "apologize" in (m.get("content") or "").lower()
            for m in conversation_history[-2:]
        ):
            llm_messages.append(
                {
                    "role": "system",
                    "content": "SYSTEM NOTE: Search tools are now back online. Please use them for the user's request.",
                }
            )

        # Quota-Aware Tool Injection
        # If we are over the daily limit, we respond using LLM knowledge without tools
        effective_tools = (
            tools_metadata if (tools_metadata and not is_offline_mode) else None
        )

        if is_offline_mode:
            llm_messages.append(
                {
                    "role": "system",
                    "content": "SYSTEM NOTE: Daily live search quota (100 req) reached. You are now in KNOWLEDGE-ONLY mode. Inform the user gracefully if they ask for live searches.",
                }
            )

        while True:
            if iteration >= 5:
                ctx.logger.warning(
                    f"[{sender[:16]}...] Reasoning loop hit maximum iteration limit (5). Breaking to prevent infinite loop or quota drain."
                )
                final_answer_override = "I hit an internal processing limit trying to search for that. Here is what I found so far; please be a bit more specific."
                # Break natively; it will fall through to final answer generation
                # using the content from the previous turns.
                break

            iteration += 1

            # One single call — let the model choose naturally, but grounded by the hint
            response = await _openai_client.chat.completions.create(
                model=os.getenv("ASI1_MODEL", "asi1"),
                messages=llm_messages if iteration == 1 else conversation_history,
                tools=effective_tools,
            )

            assistant_msg = response.choices[0].message

            # Persist the assistant's turn (may contain tool_calls or text)
            # Convert to dict for storage serialisation
            assistant_dict = {
                "role": "assistant",
                "content": assistant_msg.content,
            }
            if assistant_msg.tool_calls:
                assistant_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in assistant_msg.tool_calls
                ]
            conversation_history.append(assistant_dict)

            # If no tool calls were made, we have the final response
            if not assistant_msg.tool_calls:
                ctx.logger.info(
                    f"[{sender[:16]}...] LLM provided a direct response without tool calls."
                )
                break

            # 5. Execute all requested remote MCP tool calls
            ctx.logger.info(
                f"[{sender[:16]}...] LLM requested {len(assistant_msg.tool_calls)} tool call(s):"
            )

            for tc in assistant_msg.tool_calls:
                ctx.logger.info(
                    f"  → Tool: '{tc.function.name}' | Args: {tc.function.arguments}"
                )
            tool_results, network_calls = await execute_mcp_tools(
                ctx.storage, assistant_msg.tool_calls
            )

            # Update today's quota usage
            current_usage += network_calls
            ctx.storage.set(quota_key, current_usage)
            if network_calls > 0:
                ctx.logger.info(
                    f"Quota Updated: {current_usage}/100 (+{network_calls})"
                )

            # Feed tool results back into the conversation history
            # Truncate 'offers' to top 10 before passing to LLM (prevents token overflow and duplication)
            all_offers: list[dict] = []
            for tool_call_id, content in tool_results:
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "offers" in parsed:
                        parsed["offers"] = parsed["offers"][:10]
                        content = json.dumps(parsed)
                        all_offers.extend(parsed["offers"])
                    elif isinstance(parsed, dict) and "id" in parsed:
                        all_offers.append(parsed)
                except Exception:
                    pass

                preview = content[:300] + "..." if len(content) > 300 else content
                ctx.logger.info(f"  ← Tool result [{tool_call_id[:12]}...]: {preview}")
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": content,
                }
                conversation_history.append(tool_msg)

            # Build a rich hint map with all display fields for side-by-side card layout
            if all_offers:
                try:
                    hint_lines = []
                    for item in all_offers:
                        title = item.get("title", "")
                        img = item.get("image_url", "")
                        book = item.get("url") or item.get("booking_url", "")
                        price_obj = item.get("price")
                        if isinstance(price_obj, dict):
                            price = (
                                item.get("price_formatted")
                                or f"€{price_obj.get('eur', price_obj.get('gbp', '??'))}"
                            )
                        else:
                            price = item.get("price_formatted") or "—"
                        rating = item.get("rating", "")
                        reviews = item.get("ratings_count", "")
                        dur_mins = item.get("duration_minutes")
                        duration = f"{dur_mins} min" if dur_mins else ""
                        avail = item.get("first_available", "")
                        # Extract clean domain name for the CTA label
                        try:
                            from urllib.parse import urlparse

                            provider = urlparse(book).netloc.replace("www.", "")
                        except Exception:
                            provider = "book now"
                        # Parse dimensions from CDN URL e.g. .../200x200?returnCrop=yes → w=200, h=200
                        import re as _re

                        _dim = _re.search(r"/(\d+)x(\d+)", img)
                        img_w, img_h = (
                            (_dim.group(1), _dim.group(2)) if _dim else ("", "")
                        )
                        hint_lines.append(
                            f'"{title}" | img={img} | img_w={img_w} | img_h={img_h} | book={book} | provider={provider} | price=From {price} | '
                            f"rating={rating}⭐ ({reviews} reviews) | duration={duration} | available_from={avail}"
                        )
                    if hint_lines:
                        hint_map = "\n".join(hint_lines)
                        # Build a sample img tag using the first item's dimensions for the template
                        first = all_offers[0] if all_offers else {}
                        _s = _re.search(r"/(\d+)x(\d+)", first.get("image_url", ""))
                        tpl_w, tpl_h = (_s.group(1), _s.group(2)) if _s else ("W", "H")
                        conversation_history.append(
                            {
                                "role": "system",
                                "content": (
                                    "SYSTEM: For every experience you mention, render it using this EXACT Markdown card format.\n"
                                    "Copy the structure precisely — only substitute the data fields:\n\n"
                                    f'| <img src="[image_url]" width="{tpl_w}" height="{tpl_h}"/> | **[Title]**<br/>'
                                    "[1-2 sentence summary, max 300 chars, derived from the title/tour type/destination in the tool result. No invented facts.]<br/>"
                                    "💰 **[price]** &nbsp; ⭐ **[rating]** *([reviews] reviews)*<br/>"
                                    "📅 Available from [available_from]<br/><br/>"
                                    "[🎟️ Book on [provider] →]([book_url]) |\n"
                                    "|---|---|\n\n"
                                    "Rules:\n"
                                    "- Use ONLY the price/rating/image data from the reference below — never invent those.\n"
                                    "- The summary is the one field you write yourself, grounded in real knowledge.\n"
                                    "- Use the img_w and img_h from each item's reference data for its width/height.\n"
                                    "- Omit ⏱️ line entirely if duration is empty.\n"
                                    "- Keep your ## category headers with emoji above each group of cards.\n"
                                    "- Do NOT add a separate 'Discovered Experiences' section.\n"
                                    f"Reference data:\n{hint_map}"
                                ),
                            }
                        )
                except Exception:
                    pass

            # Nudge to synthesize (prevents silent loops)
            conversation_history.append(
                {
                    "role": "system",
                    "content": "SYSTEM: Tool results received. Now synthesize them into a clear, helpful categorized answer for the user. Embed images inline.",
                }
            )

        # 6. Persist the updated session history for this sender
        # Filter out transient system hints to prevent context drift in future turns
        persisted_history = [
            m
            for m in conversation_history
            if not (
                m.get("role") == "system"
                and str(m.get("content", "")).startswith("SYSTEM")
            )
        ]
        ctx.storage.set(
            history_key, {"messages": persisted_history, "last_active": time.time()}
        )

        # 7. Send the final answer back — session stays open for follow-ups
        #    Images are now embedded inline by the LLM, no separate block needed.
        fallback_msg = locals().get(
            "final_answer_override", "I've gathered these results for you."
        )
        final_answer = assistant_msg.content or fallback_msg
        await ctx.send(sender, _build_send_response(final_answer, end_session=False))

    except Exception as e:
        ctx.logger.error(f"Reasoning loop error for {sender[:16]}...: {e}")
        await ctx.send(
            sender,
            _build_send_response(
                "Sorry, something went wrong on my end. Please try again.",
                end_session=False,
            ),
        )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Ack from {sender[:16]}... for msg {msg.acknowledged_msg_id}")

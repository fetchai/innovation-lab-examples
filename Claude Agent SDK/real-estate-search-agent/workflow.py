"""
workflow.py — Core agent workflow using the Anthropic Messages API directly.

Replaces claude_agent_sdk with a standard agentic tool-use loop that works
anywhere (Agentverse, local, any server) without extra dependencies.

Architecture:
  parse_search_intent()  → single-turn Claude call to extract structured JSON
  run_agent_loop()       → multi-turn tool-use loop (search → sheet → summary)
  run_workflow()         → entry point for new searches
  resume_workflow()      → entry point for follow-up searches (in-memory sessions)
"""

import asyncio
import json
import re
import os  # noqa: F401
import time
from datetime import datetime  # noqa: F401
from dataclasses import dataclass, field  # noqa: F401
from typing import Optional

import anthropic

from scraper import SearchInput, fetch_listings
from sheets import GoogleAuthRequiredError, create_listings_sheet

# ─────────────────────────────────────────────────────────────────────────────
# In-memory session store (replaces sessions.json — no disk I/O on Agentverse)
# Key: user_id  →  Value: list of messages for conversation continuity
# ─────────────────────────────────────────────────────────────────────────────
_sessions: dict[str, list] = {}

# Rate limiting — HomeHarvest can get blocked if called too fast
_last_search_time: float = 0.0
SEARCH_COOLDOWN_SECONDS = 8


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class WorkflowInput:
    user_request: str
    user_id: str = "default"


@dataclass
class WorkflowResult:
    sheet_url: str
    summary: str
    num_results: int
    session_id: Optional[str] = None
    # Set when sheet creation is deferred pending payment
    pending_df: Optional[object] = None  # pandas DataFrame
    pending_search: Optional["SearchInput"] = None


# ─────────────────────────────────────────────────────────────────────────────
# Tool schemas — passed to Claude via the tools= parameter
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_listings",
        "description": (
            "Search real estate listings from HomeHarvest (Zillow, Realtor.com, Redfin). "
            "Call this first with the parsed search criteria."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City, State or zip code",
                },
                "listing_type": {
                    "type": "string",
                    "enum": ["for_sale", "for_rent", "sold"],
                },
                "min_price": {"type": "integer", "description": "Minimum price in USD"},
                "max_price": {"type": "integer", "description": "Maximum price in USD"},
                "min_beds": {"type": "integer"},
                "max_beds": {"type": "integer"},
                "min_sqft": {"type": "integer"},
                "max_sqft": {"type": "integer"},
                "property_type": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["single_family", "condo", "townhouse", "multi_family"],
                    },
                },
                "past_days": {
                    "type": "integer",
                    "description": "Listings from last N days (default 30)",
                },
            },
            "required": ["location", "listing_type"],
        },
    },
    {
        "name": "create_sheet",
        "description": (
            "Create a Google Sheet with the listings found by search_listings. "
            "Only call this after search_listings returns results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# Tools used when sheet creation is deferred pending payment
SEARCH_ONLY_TOOLS = [t for t in TOOLS if t["name"] == "search_listings"]

SEARCH_ONLY_SYSTEM_PROMPT = """You are a real estate assistant agent.

Your job:
1. Call search_listings with the user's criteria.
2. Return a concise summary of the results: total count, price range, and average price.

Rules:
- Only call search_listings. No other tools are available in this step.
- Your summary must contain ONLY the search results (counts, prices, neighborhoods).
- Do NOT mention Google Sheets, payment, tools you lack, or next steps. The system handles that."""


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Parse natural language → structured SearchInput
# ─────────────────────────────────────────────────────────────────────────────


async def parse_search_intent(user_request: str) -> SearchInput:
    client = anthropic.Anthropic()

    prompt = f"""Parse this real estate search request into structured JSON.

User request: "{user_request}"

Return ONLY valid JSON with these fields (omit fields not mentioned):
{{
  "location": "City, State OR zip code (required)",
  "listing_type": "for_sale | for_rent | sold  (default: for_sale)",
  "min_price": integer or null,
  "max_price": integer or null,
  "min_beds": integer or null,
  "max_beds": integer or null,
  "min_sqft": integer or null,
  "max_sqft": integer or null,
  "property_type": ["single_family","condo","townhouse","multi_family"] or null,
  "past_days": integer (default 30)
}}

Examples:
- "3 bed house in Austin TX under 600k" → {{"location":"Austin, TX","listing_type":"for_sale","min_beds":3,"max_price":600000}}
- "rent apartment NYC 2 bed" → {{"location":"New York, NY","listing_type":"for_rent","min_beds":2,"max_beds":2}}

Return only the JSON, no explanation."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",  # Fast + cheap for parsing
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```json\s*|^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    parsed = json.loads(raw)

    return SearchInput(
        location=parsed.get("location", ""),
        listing_type=parsed.get("listing_type", "for_sale"),
        min_price=parsed.get("min_price"),
        max_price=parsed.get("max_price"),
        min_beds=parsed.get("min_beds"),
        max_beds=parsed.get("max_beds"),
        min_sqft=parsed.get("min_sqft"),
        max_sqft=parsed.get("max_sqft"),
        property_type=parsed.get("property_type"),
        past_days=parsed.get("past_days", 30),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tool execution — called when Claude requests a tool
# ─────────────────────────────────────────────────────────────────────────────


# Shared state within a single workflow run
@dataclass
class _RunState:
    search: Optional[SearchInput] = None
    user_id: str = "default"
    df: object = None  # pandas DataFrame or None
    sheet_url: str = ""
    num_results: int = 0
    last_error: str = ""


async def _execute_tool(tool_name: str, tool_input: dict, state: _RunState) -> str:
    """Execute a tool call from Claude and return result as a JSON string."""
    global _last_search_time

    # ── search_listings ──────────────────────────────────────────────────────
    if tool_name == "search_listings":
        # Rate limiting
        now = time.time()
        elapsed = now - _last_search_time
        if _last_search_time > 0 and elapsed < SEARCH_COOLDOWN_SECONDS:
            wait = round(SEARCH_COOLDOWN_SECONDS - elapsed, 1)
            return json.dumps(
                {
                    "status": "rate_limited",
                    "message": f"Please wait {wait}s before searching again.",
                }
            )

        _last_search_time = time.time()

        # Build SearchInput from Claude's tool_input
        search = SearchInput(
            location=tool_input.get(
                "location", state.search.location if state.search else ""
            ),
            listing_type=tool_input.get("listing_type", "for_sale"),
            min_price=tool_input.get("min_price"),
            max_price=tool_input.get("max_price"),
            min_beds=tool_input.get("min_beds"),
            max_beds=tool_input.get("max_beds"),
            min_sqft=tool_input.get("min_sqft"),
            max_sqft=tool_input.get("max_sqft"),
            property_type=tool_input.get("property_type"),
            past_days=tool_input.get("past_days", 30),
        )
        state.search = search

        print(f"[Tool] search_listings → {search.location} | {search.listing_type}")
        try:
            df = await asyncio.to_thread(fetch_listings, search)
            state.df = df
            state.num_results = len(df) if df is not None and not df.empty else 0
            state.last_error = ""

            if df is None or df.empty:
                return json.dumps(
                    {
                        "status": "no_results",
                        "message": f"No listings found in {search.location} with the given filters.",
                        "num_results": 0,
                        "location": search.location,
                    }
                )

            preview = json.loads(df.head(5).to_json(orient="records"))
            return json.dumps(
                {
                    "status": "success",
                    "num_results": len(df),
                    "location": search.location,
                    "listing_type": search.listing_type,
                    "price_min": (lambda v: None if v != v else int(v))(
                        df["Price ($)"].min()
                    )
                    if "Price ($)" in df.columns
                    else None,
                    "price_max": (lambda v: None if v != v else int(v))(
                        df["Price ($)"].max()
                    )
                    if "Price ($)" in df.columns
                    else None,
                    "price_avg": (lambda v: None if v != v else int(v))(
                        df["Price ($)"].mean()
                    )
                    if "Price ($)" in df.columns
                    else None,
                    "sample_listings": preview,
                }
            )

        except Exception as e:
            print(f"[Tool] search_listings error: {e}")
            state.df = None
            state.num_results = 0
            state.last_error = str(e)
            return json.dumps({"status": "error", "error": str(e), "num_results": 0})

    # ── create_sheet ─────────────────────────────────────────────────────────
    elif tool_name == "create_sheet":
        if state.df is None or (hasattr(state.df, "empty") and state.df.empty):
            return json.dumps(
                {
                    "status": "error",
                    "error": "No listings data — run search_listings first.",
                }
            )

        print("[Tool] create_sheet → writing to Google Sheets...")
        try:
            sheet_url = await asyncio.to_thread(
                create_listings_sheet,
                state.df,
                state.search.location,
                state.search.listing_type,
                state.user_id,
            )
            state.sheet_url = sheet_url
            state.last_error = ""
            print(f"[Tool] Sheet created: {sheet_url}")
            return json.dumps(
                {"status": "success", "sheet_url": sheet_url, "num_rows": len(state.df)}
            )

        except GoogleAuthRequiredError as e:
            state.last_error = str(e)
            print(f"[Tool] create_sheet auth required: {e}")
            return json.dumps({"status": "auth_required", "error": str(e)})
        except Exception as e:
            state.last_error = str(e)
            print(f"[Tool] create_sheet error: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Agentic tool-use loop
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a real estate assistant agent.

Your job:
1. Call search_listings with the user's criteria
2. Review the results
3. Call create_sheet to save results to Google Sheets
4. Finish with a concise summary: number of results, price range, average price, and the sheet URL

Always complete both steps — search then sheet — before giving your final summary.
If search returns no results, explain why and suggest broader criteria."""


async def run_agent_loop(
    search: SearchInput,
    user_id: str,
    prior_messages: Optional[list] = None,
    tools: Optional[list] = None,
    system_prompt: Optional[str] = None,
) -> WorkflowResult:
    """
    Agentic tool-use loop using the Anthropic Messages API directly.
    Handles multiple tool calls per turn, accumulates conversation history
    for session continuity, and runs up to max_iterations to prevent runaway loops.
    """
    client = anthropic.Anthropic()
    state = _RunState(search=search, user_id=user_id)

    user_prompt = (
        f"Find real estate listings and create a Google Sheet:\n"
        f"- Location     : {search.location}\n"
        f"- Listing type : {search.listing_type}\n"
        f"- Price range  : ${search.min_price or 'any'} – {search.max_price or 'any'}\n"
        f"- Beds         : {search.min_beds or 'any'}+\n"
        f"- Property type: {', '.join(search.property_type) if search.property_type else 'any'}\n\n"
        f"Call search_listings first, then create_sheet."
    )

    # Seed messages — prepend history if resuming a session
    messages = list(prior_messages or [])
    messages.append({"role": "user", "content": user_prompt})

    final_summary = ""
    max_iterations = 8  # Safety cap

    for iteration in range(max_iterations):
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            system=system_prompt or SYSTEM_PROMPT,
            tools=tools or TOOLS,
            messages=messages,
        )

        # Append Claude's response to history
        messages.append({"role": "assistant", "content": response.content})

        # ── Done — Claude gave a final text response ──────────────────────
        if response.stop_reason == "end_turn":
            # Extract the last text block as the final summary
            for block in response.content:
                if hasattr(block, "text"):
                    final_summary = block.text
            break

        # ── Tool use — execute all tool calls in this turn ────────────────
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"[Agent] Claude calling: {block.name}")
                    result_str = await _execute_tool(block.name, block.input, state)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        }
                    )

            # Feed all results back to Claude in one user turn
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        print(f"[Agent] Unexpected stop_reason: {response.stop_reason}")
        break

    # Save conversation history for this user (session continuity)
    _sessions[user_id] = messages

    if not final_summary:
        if state.sheet_url and state.num_results > 0:
            final_summary = (
                f"Found {state.num_results} listings in {search.location}. "
                f"Google Sheet: {state.sheet_url}"
            )
        elif state.last_error:
            final_summary = (
                f"Found {state.num_results} listings in {search.location}, but sheet creation failed. "
                f"{state.last_error}"
            )
        else:
            final_summary = (
                f"No listings found in {search.location} matching your criteria."
            )

    return WorkflowResult(
        sheet_url=state.sheet_url,
        summary=final_summary,
        num_results=state.num_results,
        session_id=user_id,
        # Populated when sheet creation is deferred (payment-gated mode)
        pending_df=state.df if not state.sheet_url else None,
        pending_search=state.search if not state.sheet_url else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────


async def run_workflow(input_data: WorkflowInput) -> WorkflowResult:
    """Start a fresh search. Clears any saved session for this user_id."""
    print(f"\n🏠 New search — user: {input_data.user_id}")
    print(f'   Request: "{input_data.user_request}"')

    search = await parse_search_intent(input_data.user_request)
    print(
        f"   Parsed: {search.location} | {search.listing_type} | "
        f"${search.min_price or 0:,}–{'∞' if not search.max_price else f'${search.max_price:,}'} | "
        f"{search.min_beds or 'any'}+ beds"
    )

    if not search.location:
        return WorkflowResult(
            sheet_url="",
            summary="Could not determine a location. Please include a city, state, or zip code.",
            num_results=0,
        )

    # Clear old session — this is a fresh search
    _sessions.pop(input_data.user_id, None)
    return await run_agent_loop(search, user_id=input_data.user_id)


async def resume_workflow(input_data: WorkflowInput) -> WorkflowResult:
    """
    Resume a previous search session for this user_id.
    Claude gets the full prior conversation history so it remembers context.
    Falls back to a fresh search if no session exists.
    """
    prior_messages = _sessions.get(input_data.user_id)

    if prior_messages:
        print(f"\n🔄 Resuming session for user: {input_data.user_id}")
        search = await parse_search_intent(input_data.user_request)
        return await run_agent_loop(
            search, user_id=input_data.user_id, prior_messages=prior_messages
        )
    else:
        print(f"\n⚠️  No session for '{input_data.user_id}' — starting fresh")
        return await run_workflow(input_data)


async def run_search_only(input_data: WorkflowInput) -> WorkflowResult:
    """Search listings without creating a Google Sheet.

    Used when payment is required: the caller holds on to result.pending_df
    and result.pending_search, creates the sheet after CommitPayment is received.
    """
    print(f"\n🔍 Search-only (payment-gated) — user: {input_data.user_id}")
    print(f'   Request: "{input_data.user_request}"')

    search = await parse_search_intent(input_data.user_request)
    if not search.location:
        return WorkflowResult(
            sheet_url="",
            summary="Could not determine a location. Please include a city, state, or zip code.",
            num_results=0,
        )

    # Clear old session so follow-ups start clean
    _sessions.pop(input_data.user_id, None)
    return await run_agent_loop(
        search,
        user_id=input_data.user_id,
        tools=SEARCH_ONLY_TOOLS,
        system_prompt=SEARCH_ONLY_SYSTEM_PROMPT,
    )

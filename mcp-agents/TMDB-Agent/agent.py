"""Tonight's Pick — uAgent deployed on Fetch.ai Agentverse.

Conversation flow:
  1. User describes mood/context.
  2. Agent asks one follow-up (vibe + reference movie) if intake incomplete.
  3. Agent calls ASI1 with tool schemas; executes the tool-use loop.
  4. Agent replies with 3-4 picks grouped by vibe.

Session state stored in ctx.storage:
  vibe        — e.g. "on-edge"
  vibe2       — optional second vibe for "we can't agree" mode
  who         — e.g. "partner", "solo", "family"
  reference   — e.g. "Parasite"
  rejections  — JSON list of movie IDs the user has rejected
  history     — JSON list of {role, content} conversation turns
  media_type  — "movie" (default) or "tv"
  max_runtime — optional int (minutes) for time-boxed discovery
  watchlist   — JSON list of {label, text} saved recommendation sets
  seen_titles — JSON list of movie/show titles already seen
"""

from __future__ import annotations
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

from uagents import Agent, Context, Protocol  # noqa: E402
from uagents.setup import fund_agent_if_low  # noqa: E402
from uagents_core.contrib.protocols.chat import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from openai import AsyncOpenAI  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from tonights_pick_mcp.tools import (  # noqa: E402
    search_movies,
    get_similar,
    get_recommendations,
    resolve_mood,
    get_trending,
    search_by_keyword,
    get_movie_details,
    check_watch_providers,
    search_tv,
    get_similar_tv,
    get_tv_details,
    resolve_mood_tv,
    check_tv_watch_providers,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ASI1_API_KEY = os.environ.get("ASI_ONE_API_KEY", "")
ASI1_BASE_URL = "https://api.asi1.ai/v1"
ASI1_MODEL = "asi1"
AGENT_SEED = os.environ.get("AGENT_SEED", "tonights-pick-agent-seed-v1")
AGENT_PORT = int(os.environ.get("AGENT_PORT", 8001))

asi1_client = AsyncOpenAI(api_key=ASI1_API_KEY, base_url=ASI1_BASE_URL)

# ---------------------------------------------------------------------------
# Tool registries
# ---------------------------------------------------------------------------

MOVIE_TOOL_FUNCTIONS: dict[str, Any] = {
    "search_movies": search_movies,
    "get_similar": get_similar,
    "get_recommendations": get_recommendations,
    "resolve_mood": resolve_mood,
    "get_trending": get_trending,
    "search_by_keyword": search_by_keyword,
    "get_movie_details": get_movie_details,
    "check_watch_providers": check_watch_providers,
}

TV_TOOL_FUNCTIONS: dict[str, Any] = {
    "search_tv": search_tv,
    "get_similar_tv": get_similar_tv,
    "get_tv_details": get_tv_details,
    "resolve_mood_tv": resolve_mood_tv,
    "get_trending": get_trending,
    "check_tv_watch_providers": check_tv_watch_providers,
}

MOVIE_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_movies",
            "description": "Search TMDB for movies matching a title. Use to resolve a title to its TMDB ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_similar",
            "description": "Get movies similar to a given TMDB movie ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["movie_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendations",
            "description": "Get TMDB personalised recommendations for a movie ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["movie_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_mood",
            "description": (
                "Discover movies matching a mood/vibe. "
                "Vibes: on-edge, slow-burn, dark, intense, feel-good, romantic, "
                "cosy, mind-bending, scary, funny, action-packed, tearjerker. "
                "Pass max_runtime (minutes) to enforce a runtime cap."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vibe": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                    "max_runtime": {
                        "type": "integer",
                        "description": "Max runtime in minutes",
                    },
                },
                "required": ["vibe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trending",
            "description": "Fetch trending movies or TV shows this week.",
            "parameters": {
                "type": "object",
                "properties": {
                    "media_type": {
                        "type": "string",
                        "enum": ["movie", "tv"],
                        "default": "movie",
                    },
                    "window": {
                        "type": "string",
                        "enum": ["day", "week"],
                        "default": "week",
                    },
                    "limit": {"type": "integer", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_keyword",
            "description": "Find movies tagged with a keyword (e.g. 'heist', 'revenge', 'psychological').",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_movie_details",
            "description": "Get full details (runtime, genres, tagline) for a single TMDB movie ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_id": {"type": "integer"},
                },
                "required": ["movie_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_watch_providers",
            "description": (
                "Check streaming availability for a list of movie IDs. "
                "country: ISO 3166-1 alpha-2 (e.g. 'US', 'GB')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_ids": {"type": "array", "items": {"type": "integer"}},
                    "country": {"type": "string", "default": "US"},
                },
                "required": ["movie_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call this when you have your final picks. Supply raw data only — no formatting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "picks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "vibe": {
                                    "type": "string",
                                    "description": "Short vibe label, e.g. 'slow-burn dread'",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Movie title only, no year",
                                },
                                "runtime": {
                                    "type": "string",
                                    "description": "Runtime, e.g. '119 min'",
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "One sentence why this fits",
                                },
                                "streaming": {
                                    "type": "string",
                                    "description": "Streaming service name(s)",
                                },
                            },
                            "required": ["vibe", "title", "reason", "streaming"],
                        },
                    },
                },
                "required": ["picks"],
            },
        },
    },
]

TV_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_tv",
            "description": "Search TMDB for TV shows matching a title. Use to resolve a title to its TMDB ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_similar_tv",
            "description": "Get TV shows similar to a given TMDB show ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tv_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["tv_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tv_details",
            "description": "Get full details (seasons, episode runtime, genres) for a TMDB TV show ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tv_id": {"type": "integer"},
                },
                "required": ["tv_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_mood_tv",
            "description": (
                "Discover TV shows matching a mood/vibe. "
                "Vibes: on-edge, slow-burn, dark, intense, feel-good, romantic, "
                "cosy, mind-bending, scary, funny, action-packed, tearjerker."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vibe": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["vibe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trending",
            "description": "Fetch trending TV shows this week.",
            "parameters": {
                "type": "object",
                "properties": {
                    "media_type": {"type": "string", "enum": ["tv"], "default": "tv"},
                    "window": {
                        "type": "string",
                        "enum": ["day", "week"],
                        "default": "week",
                    },
                    "limit": {"type": "integer", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_tv_watch_providers",
            "description": "Check streaming availability for a list of TV show IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tv_ids": {"type": "array", "items": {"type": "integer"}},
                    "country": {"type": "string", "default": "US"},
                },
                "required": ["tv_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call this when you have your final picks. Supply raw data only — no formatting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "picks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "vibe": {
                                    "type": "string",
                                    "description": "Short vibe label, e.g. 'slow-burn dread'",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Show title only",
                                },
                                "runtime": {
                                    "type": "string",
                                    "description": "e.g. '3 seasons, ~45 min/ep'",
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "One sentence why this fits",
                                },
                                "streaming": {
                                    "type": "string",
                                    "description": "Streaming service name(s)",
                                },
                            },
                            "required": ["vibe", "title", "reason", "streaming"],
                        },
                    },
                },
                "required": ["picks"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_MOVIE_SYSTEM_PROMPT = """You are Tonight's Pick — a conversational movie recommendation agent.

Your goal: find 3-4 streaming-ready movies that match the user's mood and viewing context.

Rules:
- Resolve reference titles to IDs first, then use those IDs.
- Use at most 2-3 discovery calls (resolve_mood, get_similar, search_by_keyword), then stop.
- Call check_watch_providers ONCE on all candidates together.
- Only recommend movies available on at least one streaming service.
- Get runtime via get_movie_details for your final picks.
- Never recommend a movie the user has already rejected or already seen.
- Call finish with raw data fields (vibe, title, runtime, reason, streaming). Do not format anything.
- Never call more than 6 tools total.
"""

_TV_SYSTEM_PROMPT = """You are Tonight's Pick — a conversational TV show recommendation agent.

Your goal: find 3-4 streaming-ready TV shows that match the user's mood and viewing context.

Rules:
- Resolve reference show titles to IDs first.
- Use at most 2-3 discovery calls (resolve_mood_tv, get_similar_tv), then stop.
- Call check_tv_watch_providers ONCE on all candidates together.
- Only recommend shows available on at least one streaming service.
- Get seasons/runtime via get_tv_details for your final picks.
- Never recommend a show the user has already rejected or already seen.
- Call finish with raw data fields (vibe, title, runtime, reason, streaming). Do not format anything.
- Never call more than 6 tools total.
"""

# ---------------------------------------------------------------------------
# uAgent setup
# ---------------------------------------------------------------------------

agent = Agent(
    name="tonights-pick",
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
)

fund_agent_if_low(agent.wallet.address())

chat_proto = Protocol(spec=chat_protocol_spec)

FEATURE_HINT = """

You can also:
- Save a pick: "save [title]"
- View your watchlist: "show my watchlist"
- Skip titles you've seen: "mark [title] as seen"
- Filter by runtime: "under 90 minutes"
- Switch to TV: "something to binge"
- Mixed moods: "I want dark, they want romantic"
"""

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _load_state(ctx: Context) -> dict:
    return {
        "vibe": ctx.storage.get("vibe") or "",
        "vibe2": ctx.storage.get("vibe2") or "",
        "who": ctx.storage.get("who") or "",
        "reference": ctx.storage.get("reference") or "",
        "rejections": json.loads(ctx.storage.get("rejections") or "[]"),
        "history": json.loads(ctx.storage.get("history") or "[]"),
        "media_type": ctx.storage.get("media_type") or "movie",
        "max_runtime": ctx.storage.get("max_runtime"),
        "watchlist": json.loads(ctx.storage.get("watchlist") or "[]"),
        "seen_titles": json.loads(ctx.storage.get("seen_titles") or "[]"),
        "last_reply": ctx.storage.get("last_reply") or "",
    }


def _save_state(ctx: Context, state: dict) -> None:
    ctx.storage.set("vibe", state["vibe"])
    ctx.storage.set("vibe2", state["vibe2"])
    ctx.storage.set("who", state["who"])
    ctx.storage.set("reference", state["reference"])
    ctx.storage.set("rejections", json.dumps(state["rejections"]))
    ctx.storage.set("history", json.dumps(state["history"]))
    ctx.storage.set("media_type", state["media_type"])
    if state["max_runtime"] is not None:
        ctx.storage.set("max_runtime", state["max_runtime"])
    ctx.storage.set("watchlist", json.dumps(state["watchlist"]))
    ctx.storage.set("seen_titles", json.dumps(state["seen_titles"]))
    ctx.storage.set("last_reply", state["last_reply"])


# ---------------------------------------------------------------------------
# Intent detection (runs before normal intake)
# ---------------------------------------------------------------------------


def _detect_special_intent(text: str) -> str | None:
    """Return a special intent string or None for normal recommendation flow."""
    lower = text.lower()

    # --- Mark as seen (check before save to avoid conflicts) ---
    if re.search(r"\bmark\b.+\bas\s+(?:seen|watched)\b", lower):
        return "add_seen"

    # --- Save to watchlist — specific title only ---
    # "save [title] to my watchlist/wishlist" or just "save [title]"
    if re.search(r"\bto\s+(my\s+|the\s+)?(watch|wish)list\b", lower):
        return "save_watchlist"

    # "save <specific title>" — starts with save + a non-pronoun word
    if re.match(r"^save\s+(?!it\b|that\b|them\b|those\b|this\b)\w", lower):
        return "save_watchlist"

    # --- Show watchlist ---
    watchlist_show = [
        "show watchlist",
        "show my watchlist",
        "show wishlist",
        "show my wishlist",
        "what's saved",
        "what did i save",
        "show my list",
        "my watchlist",
        "my wishlist",
    ]
    if any(p in lower for p in watchlist_show):
        return "show_watchlist"

    # --- Show seen list ---
    seen_show = ["show seen", "what have i seen", "my seen list", "show my seen"]
    if any(p in lower for p in seen_show):
        return "show_seen"

    return None


def _extract_specific_title(text: str) -> str | None:
    """Pull a specific title out of 'save X to my watchlist/wishlist' style messages."""
    lower = text.lower()
    cleaned = re.sub(r"\s+to\s+(my\s+|the\s+)?(watch|wish)list.*$", "", lower).strip()
    cleaned = re.sub(r"^(save|add)\s+", "", cleaned).strip()
    if cleaned and cleaned not in {"it", "that", "them", "those", "this"}:
        idx = text.lower().find(cleaned)
        if idx != -1:
            return text[idx : idx + len(cleaned)].strip(".,!?")
    return None


def _extract_mark_seen_title(text: str) -> str | None:
    """Pull title from 'mark X as seen/watched' messages."""
    m = re.search(r"\bmark\s+(.+?)\s+as\s+(?:seen|watched)\b", text, re.IGNORECASE)
    if m:
        return m.group(1).strip().strip(".,!?")
    return None


# ---------------------------------------------------------------------------
# Intake extraction
# ---------------------------------------------------------------------------

_VIBE_KEYWORDS = [
    "on-edge",
    "slow-burn",
    "dark",
    "intense",
    "feel-good",
    "romantic",
    "cosy",
    "cozy",
    "mind-bending",
    "scary",
    "funny",
    "action-packed",
    "tearjerker",
    "thriller",
    "comedy",
    "horror",
    "drama",
]


def _extract_intake(text: str, state: dict) -> dict:
    """Extract vibe/who/reference/media_type/max_runtime/vibe2/seen from user text."""
    lower = text.lower()

    # --- media_type (TV mode) ---
    tv_signals = [
        "binge",
        "series",
        "tv show",
        "tv series",
        "show me a show",
        "something to watch on tv",
        "a series",
        "episodes",
    ]
    if any(s in lower for s in tv_signals):
        state["media_type"] = "tv"

    # --- who ---
    if not state["who"]:
        if any(
            w in lower
            for w in ["partner", "girlfriend", "boyfriend", "wife", "husband", "date"]
        ):
            state["who"] = "partner"
        elif any(w in lower for w in ["solo", "alone", "myself", "by myself"]):
            state["who"] = "solo"
        elif any(w in lower for w in ["family", "kids", "children"]):
            state["who"] = "family"
        elif any(w in lower for w in ["friend", "friends", "mates", "group"]):
            state["who"] = "friends"

    # --- primary vibe ---
    if not state["vibe"]:
        for kw in _VIBE_KEYWORDS:
            if kw in lower:
                state["vibe"] = kw
                break

    # --- second vibe (we can't agree / mixed mood) ---
    if not state["vibe2"] and state["vibe"]:
        for trigger in [
            "they want",
            "she wants",
            "he wants",
            "partner wants",
            "friend wants",
            "but also",
            "mix of",
            "and also",
        ]:
            idx = lower.find(trigger)
            if idx != -1:
                remainder = text[idx + len(trigger) :].strip()
                for kw in _VIBE_KEYWORDS:
                    if kw in remainder.lower():
                        if kw != state["vibe"]:
                            state["vibe2"] = kw
                        break
                break
        # Fallback: two distinct vibes both appear in the message
        if not state["vibe2"]:
            found = [kw for kw in _VIBE_KEYWORDS if kw in lower]
            if len(found) >= 2 and found[1] != state["vibe"]:
                state["vibe2"] = found[1]

    # --- runtime cap ---
    if state["max_runtime"] is None:
        # "under 2 hours", "less than 2 hours"
        m = re.search(
            r"(?:under|less than|max|within|no more than)\s+(\d+(?:\.\d+)?)\s*(?:hour|hr)",
            lower,
        )
        if m:
            state["max_runtime"] = int(float(m.group(1)) * 60)
        else:
            # "under 90 minutes"
            m = re.search(
                r"(?:under|less than|max|within|no more than)\s+(\d+)\s*(?:minute|min)",
                lower,
            )
            if m:
                state["max_runtime"] = int(m.group(1))
            elif (
                "short film" in lower
                or "quick watch" in lower
                or "short movie" in lower
            ):
                state["max_runtime"] = 90

    # --- reference movie/show ---
    if not state["reference"]:
        for trigger in [
            "loved ",
            "like ",
            "enjoyed ",
            "watched ",
            "similar to ",
            "fan of ",
        ]:
            # only pick up as reference if NOT preceded by "i've" / "already"
            idx = lower.find(trigger)
            if idx != -1:
                pre = lower[max(0, idx - 10) : idx]
                if "seen" in pre or "already" in pre or "i've" in pre:
                    continue
                remainder = text[idx + len(trigger) :]
                words = remainder.split()[:5]
                state["reference"] = " ".join(words).strip(".,!?")
                break

    # --- seen-it list ---
    seen_triggers = [
        "i've seen ",
        "i have seen ",
        "already seen ",
        "already watched ",
        "seen it",
        "i saw ",
    ]
    for trigger in seen_triggers:
        idx = lower.find(trigger)
        if idx != -1 and trigger not in ("seen it",):
            remainder = text[idx + len(trigger) :]
            words = remainder.split()[:5]
            title = " ".join(words).strip(".,!?")
            if title and title not in state["seen_titles"]:
                state["seen_titles"].append(title)
            break

    return state


def _intake_complete(state: dict) -> bool:
    return bool(state["vibe"])


# ---------------------------------------------------------------------------
# Tool-use loop
# ---------------------------------------------------------------------------


def _build_system_prompt(state: dict) -> str:
    base = _TV_SYSTEM_PROMPT if state["media_type"] == "tv" else _MOVIE_SYSTEM_PROMPT
    extras: list[str] = []

    if state["rejections"]:
        extras.append(f"Already rejected IDs (do not recommend): {state['rejections']}")

    if state["seen_titles"]:
        titles = ", ".join(f'"{t}"' for t in state["seen_titles"])
        extras.append(f"User has already seen these — do NOT recommend them: {titles}")

    if state["max_runtime"] and state["media_type"] == "movie":
        extras.append(
            f"RUNTIME CONSTRAINT: Only recommend movies under {state['max_runtime']} minutes. "
            f"Pass max_runtime={state['max_runtime']} to resolve_mood. Verify runtime via get_movie_details for final picks."
        )

    if state["vibe2"]:
        extras.append(
            f"MIXED MOOD: The user wants '{state['vibe']}' but their companion wants '{state['vibe2']}'. "
            f"Find picks that satisfy BOTH vibes — look for genre overlaps or films/shows that blend both moods."
        )

    if extras:
        base += "\n\n" + "\n".join(extras)
    return base


def _format_picks(picks: list[dict]) -> str:
    """Deterministic formatting — LLM supplies raw data, we control every character."""
    lines = []
    for p in picks:
        vibe = p.get("vibe", "").strip()
        title = p.get("title", "").strip()
        runtime = p.get("runtime", "").strip()
        reason = p.get("reason", "").strip().rstrip(".")
        streaming = p.get("streaming", "").strip()
        runtime_part = f" ({runtime})" if runtime else ""
        lines.append(
            f"• **{vibe}** *{title}*{runtime_part} — {reason}. Stream on: {streaming}"
        )
    return "\n\n".join(lines)


async def run_tool_loop(messages: list[dict], state: dict) -> str:
    """Call ASI1 with tool schemas; execute tool calls until finish is called."""
    tool_functions = (
        TV_TOOL_FUNCTIONS if state["media_type"] == "tv" else MOVIE_TOOL_FUNCTIONS
    )
    tool_schemas = (
        TV_TOOL_SCHEMAS if state["media_type"] == "tv" else MOVIE_TOOL_SCHEMAS
    )
    finish_only = [s for s in tool_schemas if s["function"]["name"] == "finish"]

    system_msg = {"role": "system", "content": _build_system_prompt(state)}
    loop_messages = [system_msg] + messages

    tool_call_count = 0
    FORCE_FINISH_AFTER = 8  # inject a nudge; hard-force finish after 10

    for _ in range(15):
        # After threshold, force the model to call finish
        if tool_call_count >= FORCE_FINISH_AFTER:
            loop_messages.append(
                {
                    "role": "user",
                    "content": (
                        "You have gathered enough information. "
                        "Stop searching and call finish NOW with your best picks. "
                        "Include rent/buy options if streaming isn't available."
                    ),
                }
            )
            response = await asi1_client.chat.completions.create(  # type: ignore[call-overload]
                model=ASI1_MODEL,
                messages=loop_messages,
                tools=finish_only,
                tool_choice={"type": "function", "function": {"name": "finish"}},
            )
        else:
            response = await asi1_client.chat.completions.create(  # type: ignore[call-overload]
                model=ASI1_MODEL,
                messages=loop_messages,
                tools=tool_schemas,
                tool_choice="required",
            )

        choice = response.choices[0]
        tool_calls = choice.message.tool_calls or []

        if not tool_calls:
            return (
                choice.message.content or "Sorry, I ran into trouble. Please try again."
            )

        loop_messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)

            if fn_name == "finish":
                picks = fn_args.get("picks", [])
                if picks:
                    return _format_picks(picks)
                return "Sorry, I ran into trouble finding good picks. Please try again."

            tool_call_count += 1
            fn = tool_functions.get(fn_name)
            if fn is None:
                result = json.dumps({"error": f"Unknown tool: {fn_name}"})
            else:
                try:
                    result = await fn(**fn_args)
                except Exception as exc:
                    result = json.dumps({"error": str(exc)})

            loop_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    return "Sorry, I ran into trouble finding good picks. Please try again."


# ---------------------------------------------------------------------------
# Special intent handlers
# ---------------------------------------------------------------------------


def _handle_show_watchlist(state: dict) -> str:
    if not state["watchlist"]:
        return "Your watchlist is empty. After I give you recommendations, say 'save it' or 'save [title]' to add picks."
    lines = [
        f"Your watchlist ({len(state['watchlist'])} title{'s' if len(state['watchlist']) != 1 else ''}):\n"
    ]
    for i, item in enumerate(state["watchlist"], 1):
        lines.append(f"{i}. {item['title']}")
    return "\n".join(lines)


def _handle_save_watchlist(state: dict, user_text: str = "") -> str:
    title = _extract_specific_title(user_text) if user_text else None
    if not title:
        return 'Tell me which title to save — e.g. "save The Dark Knight".'
    already = [w["title"].lower() for w in state["watchlist"]]
    if title.lower() not in already:
        state["watchlist"].append({"title": title})
    current = ", ".join(w["title"] for w in state["watchlist"])
    return f"Saved {title} to your watchlist!\n\nCurrent watchlist: {current}"


def _handle_add_seen(state: dict, user_text: str) -> str:
    title = _extract_mark_seen_title(user_text)
    if title:
        if title.lower() not in [s.lower() for s in state["seen_titles"]]:
            state["seen_titles"].append(title)
        return f"Got it — I'll skip **{title}** in all future recommendations."
    return "Which title should I mark as seen? Just tell me the name."


def _handle_show_seen(state: dict) -> str:
    if not state["seen_titles"]:
        return "Your seen list is empty. Tell me 'I've seen X' and I'll remember to skip it."
    titles = "\n".join(f"- {t}" for t in state["seen_titles"])
    return f"Movies/shows you've marked as seen:\n{titles}"


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------


def _make_chat_message(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info(f"Acknowledgement from {sender} for {msg.acknowledged_msg_id}")


@chat_proto.on_message(ChatMessage)
async def on_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    if any(isinstance(item, StartSessionContent) for item in msg.content):
        ctx.logger.info(f"Session started by {sender}")

    user_text = " ".join(
        item.text for item in msg.content if isinstance(item, TextContent)
    ).strip()
    # Strip leading @mentions (Agentverse includes the handle in the message text)
    user_text = re.sub(r"^(@\w[\w.-]*\s*)+", "", user_text).strip()
    if not user_text:
        return

    state = _load_state(ctx)
    state["history"].append({"role": "user", "content": user_text})

    # --- Special intent handling (watchlist / seen list) ---
    intent = _detect_special_intent(user_text)
    if intent == "show_watchlist":
        reply = _handle_show_watchlist(state)
        state["history"].append({"role": "assistant", "content": reply})
        _save_state(ctx, state)
        await ctx.send(sender, _make_chat_message(reply))
        return

    if intent == "save_watchlist":
        reply = _handle_save_watchlist(state, user_text)
        state["history"].append({"role": "assistant", "content": reply})
        _save_state(ctx, state)
        await ctx.send(sender, _make_chat_message(reply))
        return

    if intent == "add_seen":
        reply = _handle_add_seen(state, user_text)
        state["history"].append({"role": "assistant", "content": reply})
        _save_state(ctx, state)
        await ctx.send(sender, _make_chat_message(reply))
        return

    if intent == "show_seen":
        reply = _handle_show_seen(state)
        state["history"].append({"role": "assistant", "content": reply})
        _save_state(ctx, state)
        await ctx.send(sender, _make_chat_message(reply))
        return

    # --- Normal intake extraction ---
    state = _extract_intake(user_text, state)

    if not _intake_complete(state):
        content_type = "show" if state["media_type"] == "tv" else "movie"
        follow_up = (
            f"What's the vibe tonight — on-edge, slow-burn, dark, funny, romantic? "
            f"Any {content_type} you loved recently?"
        )
        state["history"].append({"role": "assistant", "content": follow_up})
        _save_state(ctx, state)
        await ctx.send(sender, _make_chat_message(follow_up))
        return

    # --- Run tool-use loop ---
    reply_text = await run_tool_loop(state["history"], state)
    state["last_reply"] = reply_text
    state["history"].append({"role": "assistant", "content": reply_text})
    outgoing = reply_text + FEATURE_HINT
    _save_state(ctx, state)

    await ctx.send(sender, _make_chat_message(outgoing))


agent.include(chat_proto)

if __name__ == "__main__":
    agent.run()

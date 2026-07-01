"""Twitch channel growth analysis agent.

A LangGraph pipeline that analyzes a Twitch channel and produces a growth
strategy report. The graph runs five nodes in sequence, each enriching a
shared state object:

    channel_analyzer -> content_researcher -> competitor_benchmarker
        -> gap_identifier -> strategy_generator

LLM reasoning is powered by ASI:One (via LangChain's ChatOpenAI), channel
stats come from the Twitch Helix API, and competitor research uses Tavily.
"""

import os
from typing import Optional, TypedDict

import requests
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from tavily import TavilyClient

load_dotenv()


# Shared state passed through and filled in by each node.
class GrowthState(TypedDict):
    channel_name: str
    channel_stats: Optional[dict]
    niche: Optional[str]
    competitors: Optional[list]
    gaps: Optional[list]
    final_report: Optional[str]


# ASI:One is OpenAI-compatible, so ChatOpenAI just points at its base_url.
llm = ChatOpenAI(
    model="asi1",
    base_url="https://api.asi1.ai/v1",
    api_key=os.getenv("ASI_ONE_API_KEY"),  # type: ignore[arg-type]
    temperature=0.4,
)

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def get_twitch_token() -> str:
    """Fetch an app access token via the client-credentials flow."""
    auth_response = requests.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id": os.getenv("TWITCH_CLIENT_ID"),
            "client_secret": os.getenv("TWITCH_CLIENT_SECRET"),
            "grant_type": "client_credentials",
        },
    )
    auth_response.raise_for_status()
    return auth_response.json()["access_token"]


def channel_analyzer(state: GrowthState) -> GrowthState:
    """Pull profile, category/title, and live status from Twitch; follower
    counts aren't available via app token, so also pull those via Tavily.
    """
    channel = state["channel_name"]
    token = get_twitch_token()
    headers = {
        "Client-ID": os.getenv("TWITCH_CLIENT_ID") or "",
        "Authorization": f"Bearer {token}",
    }

    users_resp = requests.get(
        "https://api.twitch.tv/helix/users",
        headers=headers,
        params={"login": channel},
    )
    users_resp.raise_for_status()
    user_data = users_resp.json()["data"]
    if not user_data:
        raise ValueError(f"Twitch channel '{channel}' not found.")
    user = user_data[0]
    broadcaster_id = user["id"]

    stats = {
        "display_name": user["display_name"],
        "description": user.get("description", ""),
        "broadcaster_type": user.get("broadcaster_type", ""),
        "created_at": user.get("created_at", ""),
    }

    channels_resp = requests.get(
        "https://api.twitch.tv/helix/channels",
        headers=headers,
        params={"broadcaster_id": broadcaster_id},
    )
    if channels_resp.ok and channels_resp.json()["data"]:
        ch = channels_resp.json()["data"][0]
        stats["current_game"] = ch.get("game_name", "")
        stats["stream_title"] = ch.get("title", "")
        stats["tags"] = ch.get("tags", [])

    streams_resp = requests.get(
        "https://api.twitch.tv/helix/streams",
        headers=headers,
        params={"user_id": broadcaster_id},
    )
    if streams_resp.ok and streams_resp.json()["data"]:
        live = streams_resp.json()["data"][0]
        stats["is_live"] = True
        stats["live_viewers"] = live.get("viewer_count")
        stats["live_game"] = live.get("game_name", "")
    else:
        stats["is_live"] = False

    external_query = f"{channel} Twitch follower count stats 2026"
    try:
        external_resp = tavily.search(external_query, max_results=5)
        stats["external_stats"] = [
            {"title": r["title"], "url": r["url"], "snippet": r.get("content", "")}
            for r in external_resp.get("results", [])
        ]
    except Exception as exc:  # noqa: BLE001 - external stats are best-effort
        stats["external_stats"] = []
        stats["external_stats_error"] = str(exc)

    state["channel_stats"] = stats
    return state


def content_researcher(state: GrowthState) -> GrowthState:
    """Use ASI:One to infer the channel's content niche from its stats."""
    stats = state["channel_stats"]
    prompt = (
        "You are a Twitch content analyst. Based on the channel data below, "
        "identify the channel's primary content niche in a short phrase "
        "(e.g. 'Just Chatting / IRL lifestyle', 'competitive FPS', "
        "'variety gaming'). Respond with ONLY the niche phrase, nothing else.\n\n"
        f"Channel data:\n{stats}"
    )
    response = llm.invoke(prompt)
    state["niche"] = str(response.content).strip()
    return state


def competitor_benchmarker(state: GrowthState) -> GrowthState:
    """Use Tavily to find top competitors / channels in the channel's niche."""
    niche = state["niche"]
    query = f"top successful Twitch streamers in {niche} 2026"
    response = tavily.search(query, max_results=5)

    competitors = [
        {"title": r["title"], "url": r["url"], "snippet": r.get("content", "")}
        for r in response.get("results", [])
    ]
    state["competitors"] = competitors
    return state


def gap_identifier(state: GrowthState) -> GrowthState:
    """Use ASI:One to compare the channel against competitors and list gaps."""
    stats = state["channel_stats"]
    niche = state["niche"]
    competitors = state["competitors"]

    competitor_text = "\n".join(
        f"- {c['title']}: {c['snippet'][:300]}" for c in (competitors or [])
    )
    prompt = (
        "You are a Twitch growth strategist. Compare the target channel to the "
        "successful competitors in its niche and identify the key gaps or "
        "opportunities the channel is missing.\n\n"
        f"Niche: {niche}\n\n"
        f"Target channel stats:\n{stats}\n\n"
        f"Competitors / niche leaders:\n{competitor_text}\n\n"
        "List 3-5 concrete gaps. Respond as a numbered list, one gap per line, "
        "with no extra commentary."
    )
    response = llm.invoke(prompt)
    gaps = [
        line.strip()
        for line in str(response.content).strip().splitlines()
        if line.strip()
    ]
    state["gaps"] = gaps
    return state


def strategy_generator(state: GrowthState) -> GrowthState:
    """Use ASI:One to synthesize everything into a growth strategy report."""
    stats = state["channel_stats"]
    niche = state["niche"]
    gaps = state["gaps"]
    competitors = state["competitors"]

    competitor_names = ", ".join(c["title"] for c in (competitors or []))
    gaps_text = "\n".join(gaps or [])
    prompt = (
        "You are a senior Twitch growth consultant. Write a clear, actionable "
        "growth strategy report for the channel below. Use markdown with these "
        "sections: 'Channel Overview', 'Niche & Positioning', 'Competitive "
        "Landscape', 'Identified Gaps', and 'Growth Strategy & Action Plan'. "
        "Make the action plan specific and prioritized.\n\n"
        "IMPORTANT: Follower and viewer figures in the stats come from the "
        "'external_stats' field, which is sourced from third-party web search "
        "(not the official Twitch API). Treat these numbers as approximate "
        "estimates that may be outdated or imprecise, and phrase them as such "
        "in the report (e.g. 'approximately', 'reportedly'). Do NOT assume the "
        "channel is inactive or has no audience just because the Twitch API "
        "fields are sparse.\n\n"
        f"Channel: {(stats or {}).get('display_name')}\n"
        f"Niche: {niche}\n"
        f"Stats: {stats}\n"
        f"Competitors: {competitor_names}\n"
        f"Identified gaps:\n{gaps_text}\n"
    )
    response = llm.invoke(prompt)
    state["final_report"] = str(response.content).strip()
    return state


def build_graph():
    """Wire the five nodes into a linear LangGraph pipeline."""
    graph = StateGraph(GrowthState)

    graph.add_node("channel_analyzer", channel_analyzer)
    graph.add_node("content_researcher", content_researcher)
    graph.add_node("competitor_benchmarker", competitor_benchmarker)
    graph.add_node("gap_identifier", gap_identifier)
    graph.add_node("strategy_generator", strategy_generator)

    graph.set_entry_point("channel_analyzer")
    graph.add_edge("channel_analyzer", "content_researcher")
    graph.add_edge("content_researcher", "competitor_benchmarker")
    graph.add_edge("competitor_benchmarker", "gap_identifier")
    graph.add_edge("gap_identifier", "strategy_generator")
    graph.add_edge("strategy_generator", END)

    return graph.compile()


app = build_graph()


if __name__ == "__main__":
    initial_state: GrowthState = {
        "channel_name": "stableronaldo",
        "channel_stats": None,
        "niche": None,
        "competitors": None,
        "gaps": None,
        "final_report": None,
    }

    result = app.invoke(initial_state)

    print("=" * 70)
    print(f"CHANNEL: {result['channel_stats'].get('display_name')}")
    print(f"NICHE: {result['niche']}")
    print(f"COMPETITORS FOUND: {len(result['competitors'])}")
    print(f"GAPS IDENTIFIED: {len(result['gaps'])}")
    print("=" * 70)
    print("\nGROWTH STRATEGY REPORT\n")
    print(result["final_report"])

import os
from tools import search_hackathon_events, fetch_event_detail, search_past_winners


def _extract_text(content) -> str:
    """
    Normalise a LangChain message .content value to a plain string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and block.get("text")
        ]
        return "\n".join(parts) if parts else str(content)
    return str(content)


def _build_model():
    """Primary model: ASI:One (OpenAI-compatible endpoint)."""
    asi1_key = os.getenv("ASI1_API_KEY")
    if asi1_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url="https://api.asi1.ai/v1",
            api_key=asi1_key,
            model="asi1-mini",
            temperature=0,
        )
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )


def _build_fallback_model():
    """
    Claude fallback when ASI:One is rate-limited / out of credits.
    Returns None if ANTHROPIC_API_KEY is not set.
    """
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model="claude-haiku-4-5", temperature=0, api_key=key)


def _build_middleware(model_call_limit: int = 30, tool_call_limit: int = 60):
    """
    Production guardrails applied inside every Deep Agents run.
    ModelRetryMiddleware: retries transient failures (rate limits, timeouts) with exponential backoff before giving up
    ModelFallbackMiddleware: if primary model keeps failing after retries, automatically switches to Claude
    ModelCallLimitMiddleware: hard cap on LLM calls per run to prevent infinite loops burning the API budget
    ToolCallLimitMiddleware: hard cap on tool calls (search/fetch) per run
    """
    from langchain.agents.middleware import (  # noqa: PLC0415
        ModelCallLimitMiddleware,
        ModelFallbackMiddleware,
        ModelRetryMiddleware,
        ToolCallLimitMiddleware,
        ToolRetryMiddleware,
    )

    middleware = [
        # 1. Retry transient failures (rate limit, timeout) with backoff
        ModelRetryMiddleware(
            max_retries=2,
            backoff_factor=2.0,
            initial_delay=2.0,
            max_delay=30.0,
        ),
        # 2. Hard cap to prevent unbounded agent loops
        ModelCallLimitMiddleware(run_limit=model_call_limit),
        ToolCallLimitMiddleware(run_limit=tool_call_limit),
        # 3. Retry web fetches
        ToolRetryMiddleware(
            max_retries=2,
            tools=["fetch_event_detail"],
            retry_on=(TimeoutError, ConnectionError),
        ),
    ]

    # 4. Fallback to Claude if ASI:One keeps failing after retries
    fallback = _build_fallback_model()
    if fallback:
        middleware.insert(1, ModelFallbackMiddleware(fallback))

    return middleware


# Sub-agent definitions (TypedDicts passed to subagents=[])
# Sub-agents only research. Parent synthesizes. Never reverse this.
_EVENT_FINDER = {
    "name": "event_finder",
    "description": (
        "Finds and researches hackathon events. Given a hackathon name or "
        "description, searches for the event page, extracts date, location, "
        "prize pool, sponsors, and tracks. Writes findings to events.md."
    ),
    "system_prompt": (
        "You are a hackathon event researcher. Your ONLY job is to find "
        "information about a specific hackathon event and write it to a file.\n\n"
        "Steps:\n"
        "1. Use search_hackathon_events to find the event\n"
        "2. Use fetch_event_detail to get the full event page\n"
        "3. Extract: event name, date, location, prize amounts, sponsor list, "
        "   prize tracks/categories, registration deadline\n"
        "4. Write ALL findings to events.md using write_file\n\n"
        "Do NOT generate project ideas. Only research and write the file."
    ),
    "tools": [search_hackathon_events, fetch_event_detail],
}

_SPONSOR_RESEARCHER = {
    "name": "sponsor_researcher",
    "description": (
        "Researches hackathon sponsors' tech stacks and APIs. Given a list "
        "of sponsors, fetches their GitHub and product pages to identify what "
        "tech they use, what APIs they expose, and what kinds of projects they "
        "reward. Writes findings to sponsors.md."
    ),
    "system_prompt": (
        "You are a sponsor research specialist. Your ONLY job is to research "
        "each sponsor's technology and write findings to sponsors.md.\n\n"
        "Steps:\n"
        "1. For each sponsor, use search_hackathon_events to find their homepage "
        "   and GitHub org\n"
        "2. Use fetch_event_detail to read their product/API page\n"
        "3. Extract: main product, primary tech stack, public APIs, "
        "   what use cases they highlight, any developer program details\n"
        "4. Write ALL findings to sponsors.md using write_file\n\n"
        "Do NOT generate project ideas. Only research and write the file."
    ),
    "tools": [search_hackathon_events, fetch_event_detail],
}

_WINNER_RESEARCHER = {
    "name": "winner_researcher",
    "description": (
        "Researches past winning projects from similar hackathons. Identifies "
        "patterns in what kinds of projects win: problem types, tech stacks, "
        "presentation approaches. Writes findings to winners.md."
    ),
    "system_prompt": (
        "You are a hackathon winning-patterns researcher. Your ONLY job is to "
        "find patterns in past winning projects and write findings to winners.md.\n\n"
        "Steps:\n"
        "1. Use search_past_winners with a descriptive query like "
        "   '<hackathon name> winners first place submissions'\n"
        "2. Also call search_past_winners for 'similar hackathon winning "
        "   projects recent' to find broader patterns\n"
        "3. Identify patterns: what problem types win, what tech stacks appear "
        "   most often in winners, what differentiates 1st vs 2nd place\n"
        "4. Write ALL findings and patterns to winners.md using write_file\n\n"
        "Do NOT generate project ideas. Only research and write the file."
    ),
    "tools": [search_past_winners, search_hackathon_events],
}


# Parent agent instructions passed as system_prompt= to create_deep_agent.
_PARENT_INSTRUCTIONS = """You are a Hackathon Competitive Intelligence specialist.

Your job: produce a competitive brief that helps a solo developer decide
what to build and why it could win a specific hackathon.

## Workflow -- follow exactly

1. Use write_todos to plan work across 3 research tracks before starting.

2. Use the task tool to delegate to each sub-agent in sequence:
   - task(agent="event_finder",       input="<hackathon query>")
   - task(agent="sponsor_researcher", input="<hackathon query> -- sponsors from events.md")
   - task(agent="winner_researcher",  input="<hackathon query>")

3. Read the output files using read_file:
   read_file("events.md")
   read_file("sponsors.md")
   read_file("winners.md")

4. YOU (the parent) synthesize everything and produce the final brief.
   Sub-agents only research. YOU generate the 3 project ideas.
   Never ask a sub-agent to generate ideas.

## Output format (use this exact structure)

### Event Summary
[date, location, prizes, tracks]

### Sponsor Analysis
[per-sponsor: tech stack, APIs, what they reward]

### Winning Patterns
[what types of projects win, key differentiators]

### Project Idea 1: [Name]
- Pitch: [one sentence]
- Tech stack: [specific libraries/APIs]
- Sponsor track: [which sponsor and why this targets them]
- Why it could win: [based on winning patterns]

### Project Idea 2: [Name]
[same structure]

### Project Idea 3: [Name]
[same structure]
"""


def run_query(hackathon_query: str) -> str:
    """
    Run the full competitive intelligence workflow (called after payment).
    """
    from deepagents import create_deep_agent  # noqa: PLC0415

    primary = _build_model()
    parent_mw = _build_middleware(model_call_limit=30, tool_call_limit=60)
    # Subagents get tighter per-call limits (one focused task each)
    sub_mw = _build_middleware(model_call_limit=12, tool_call_limit=20)

    agent = create_deep_agent(
        model=primary,
        tools=[search_hackathon_events, fetch_event_detail, search_past_winners],
        system_prompt=_PARENT_INSTRUCTIONS,
        subagents=[
            {**_EVENT_FINDER, "model": primary, "middleware": sub_mw},
            {**_SPONSOR_RESEARCHER, "model": primary, "middleware": sub_mw},
            {**_WINNER_RESEARCHER, "model": primary, "middleware": sub_mw},
        ],
        middleware=parent_mw,
    )
    result = agent.invoke({"messages": [{"role": "user", "content": hackathon_query}]})
    return _extract_text(result["messages"][-1].content)


def answer_followup(
    brief: str,
    original_query: str,
    followup: str,
    history: list[dict] | None = None,
) -> str:
    """
    Answer a follow-up question using the delivered brief and full conversation history.
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # noqa: PLC0415

    # Seed: system prompt + the brief as the first human turn so the model
    # treats the research output as established context, not part of the query.
    messages = [
        SystemMessage(
            content=(
                "You are a hackathon competitive intelligence assistant. "
                "The brief below is your ground truth for hackathon facts (sponsors, prizes, dates, project ideas). "
                "The conversation history is provided as alternating message objects — use it to honour "
                "any direction changes the user explicitly made (e.g. 'ignore idea 1, focus on Fetch.ai'). "
                "When the user refers to 'pattern 1', 'idea 1', or similar, they mean the most recently "
                "generated set in the conversation, not earlier ones. "
                "Do not re-introduce topics the user has moved away from. "
                "Use both the hackathon context and your general knowledge for detailed answers."
            )
        ),
        HumanMessage(
            content=(
                f"Original research query: {original_query}\n\n"
                f"Competitive brief:\n{brief}"
            )
        ),
    ]

    # Inject prior turns as alternating HumanMessage / AIMessage objects.
    for turn in history or []:
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=turn["content"]))
        else:
            messages.append(AIMessage(content=turn["content"]))

    messages.append(HumanMessage(content=followup))

    model = _build_model()
    try:
        return _extract_text(model.invoke(messages).content)
    except Exception as exc:
        msg = str(exc).lower()
        if "rate limit" in msg or "topup" in msg or "quota" in msg:
            fallback = _build_fallback_model()
            if fallback:
                return _extract_text(fallback.invoke(messages).content)
        raise

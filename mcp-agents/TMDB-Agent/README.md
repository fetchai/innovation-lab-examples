# 🎬 TMDB Agent for Agentverse

**A conversational movie and TV recommendation uAgent that maps natural-language moods to real streaming picks — powered by TMDB via a custom MCP server, discoverable on ASI:One through the chat protocol.**

![Architecture](https://img.shields.io/badge/Architecture-MCP%20Server%20in%20uAgent-blue)
![Protocol](https://img.shields.io/badge/Protocol-Chat%20Protocol-green)
![MCP](https://img.shields.io/badge/MCP-TMDB%20API-orange)
![AI](https://img.shields.io/badge/AI-ASI%3AOne-purple)

---

## 🏗️ Detailed Architecture

```
┌─────────────────────┐
│    ASI:One LLM      │
│   (Chat Interface)  │
└─────────┬───────────┘
          │ Chat Protocol
          ▼
┌─────────────────────┐
│      uAgent         │
│  ┌───────────────┐  │
│  │ Chat Protocol │  │  ◄─── Handles ASI:One communication
│  │   Handler     │  │
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │  Intake &     │  │  ◄─── Mood extraction + session state
│  │  Intent Layer │  │
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │  Tool-Use     │  │  ◄─── ASI:One drives tool selection
│  │  Loop (ASI1)  │  │
│  └───────┬───────┘  │
└──────────┬──────────┘
           │ async tool calls
           ▼
┌─────────────────────┐
│   TMDB MCP Tools    │
│ ┌─────────────────┐ │
│ │  resolve_mood   │ │  ◄─── Vibe → genre IDs + sort
│ │  search_movies  │ │  ◄─── Title → TMDB ID
│ │  get_similar    │ │  ◄─── Similarity chains
│ │  get_trending   │ │  ◄─── Freshness signal
│ │  check_watch_   │ │  ◄─── Live streaming availability
│ │  providers      │ │
│ └─────────────────┘ │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│    TMDB REST API    │
│  (movies, TV, watch │
│    providers)       │
└─────────────────────┘
```

---

## 🎯 What We Built: MCP Tool Layer → uAgent Wrapper

### The Architecture: Custom MCP Server Inside a uAgent

We built a **FastMCP server** (`tonights_pick_mcp/`) that exposes TMDB as typed async tools. The uAgent (`agent/agent.py`) imports these tools directly as plain async functions and drives them via an **ASI:One tool-use loop**:

```
User message
     │
     ▼
Intake extraction (mood, who, reference, runtime)
     │
     ▼
ASI:One tool-use loop
  │  ├── resolve_mood(vibe) → candidate list
  │  ├── get_similar(movie_id) → similar titles
  │  ├── check_watch_providers([ids], country) → streaming data
  │  └── finish(picks) → structured raw data
     │
     ▼
Deterministic formatter → final reply
```

The `@mcp.tool()` decoration is ignored when the tools are imported directly — the same functions serve both the FastMCP stdio server (for Claude Desktop) and the uAgent runtime.

---

## 🔧 Mood-to-TMDB Pipeline

### How a vibe becomes a recommendation

```python
# 1. User says: "something dark and slow-burn"
# 2. Intake layer extracts vibe = "slow-burn"
# 3. resolve_mood("slow-burn") calls mood_map.py:

VIBE_MAP["slow-burn"] = {
    "genres": [53, 18],          # thriller, drama
    "keywords": ["slow burn", "psychological"],
    "sort": "vote_average.desc",
}

# 4. TMDB discover endpoint:
params = {
    "with_genres": "53,18",
    "sort_by": "vote_average.desc",
    "vote_count.gte": 200,
}

# 5. Concurrent watch-provider lookup via asyncio.gather:
results = await asyncio.gather(
    *[_fetch_providers_for_movie(mid, country) for mid in movie_ids]
)
```

### Supported Vibes

| Vibe | Genres | Sort |
|---|---|---|
| `on-edge` | Thriller, Crime | vote_average |
| `slow-burn` | Thriller, Drama | vote_average |
| `dark` | Horror, Thriller, Crime | vote_average |
| `intense` | Action, Thriller | popularity |
| `feel-good` | Comedy, Romance | popularity |
| `romantic` | Romance, Comedy | vote_average |
| `cosy` | Comedy, Family | popularity |
| `mind-bending` | Sci-Fi, Thriller | vote_average |
| `scary` | Horror | popularity |
| `funny` | Comedy | popularity |
| `action-packed` | Action, Adventure | popularity |
| `tearjerker` | Drama, Romance | vote_average |

Aliases like *tense*, *gripping*, *chill*, *trippy*, *emotional*, *sad* resolve automatically.

---

## 🧠 ASI:One Tool-Use Loop

### How the agent decides what to call

The agent sends all 8 movie tools (or 6 TV tools) plus a `finish` function to ASI:One with `tool_choice="required"`. ASI:One drives the full tool-call chain — the agent just executes each call and feeds results back:

```python
async def run_tool_loop(messages, state):
    for iteration in range(15):
        response = await asi1_client.chat.completions.create(
            model="asi1",
            messages=loop_messages,
            tools=tool_schemas,
            tool_choice="required",
        )
        
        for tc in tool_calls:
            if tc.function.name == "finish":
                return _format_picks(fn_args["picks"])  # deterministic formatter
            
            result = await tool_functions[tc.function.name](**fn_args)
            loop_messages.append(tool_result(tc.id, result))
```

After 8 tool calls the agent nudges ASI:One to call `finish`. After 10 it hard-forces it.

### The `finish` tool

ASI:One never writes the user-facing text. It calls `finish` with structured raw data:

```json
{
  "picks": [
    {
      "vibe": "slow-burn dread",
      "title": "Prisoners",
      "runtime": "153 min",
      "reason": "Relentless tension and moral ambiguity — closest to Parasite's unease",
      "streaming": "Max"
    }
  ]
}
```

The agent's `_format_picks()` converts this to the final reply. Every pick looks identical regardless of which ASI:One run produced it.

---

## 💾 Session State

All conversation state is stored in `ctx.storage` (Agentverse persistent KV store):

| Key | Type | Description |
|---|---|---|
| `vibe` | str | Primary mood extracted from user input |
| `vibe2` | str | Second mood for mixed-mood group sessions |
| `who` | str | Viewing context: solo, partner, family, friends |
| `reference` | str | Reference title: *"loved Parasite"* |
| `rejections` | JSON list | TMDB IDs the user has rejected |
| `seen_titles` | JSON list | Titles to always skip |
| `watchlist` | JSON list | Saved picks |
| `media_type` | str | `"movie"` or `"tv"` |
| `max_runtime` | int | Runtime cap in minutes |
| `history` | JSON list | Full `{role, content}` conversation turns |

### Special Intents (handled without LLM calls)

| Phrase | Action |
|---|---|
| `"save The Dark Knight"` | Adds to watchlist |
| `"show my watchlist"` | Returns saved picks |
| `"mark Parasite as seen"` | Adds to seen list, skipped forever |
| `"show my seen list"` | Returns seen titles |

---

## 🌐 ASI:One Integration

### Chat Protocol Setup

```python
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent,
    StartSessionContent, EndSessionContent, chat_protocol_spec,
)

agent = Agent(
    name="tonights-pick",
    seed=AGENT_SEED,
    port=8001,
    mailbox=True,           # REQUIRED for ASI:One discoverability
)

chat_proto = Protocol(spec=chat_protocol_spec)

@chat_proto.on_message(ChatMessage)
async def on_chat_message(ctx, sender, msg):
    # Acknowledge immediately
    await ctx.send(sender, ChatAcknowledgement(...))
    
    # Extract text, run intake + tool loop, reply
    user_text = extract_text(msg)
    state = _load_state(ctx)
    state = _extract_intake(user_text, state)
    
    if _intake_complete(state):
        reply = await run_tool_loop(state["history"], state)
    else:
        reply = ask_for_missing_intake()
    
    _save_state(ctx, state)
    await ctx.send(sender, ChatMessage(content=[TextContent(text=reply)]))

agent.include(chat_proto)
```

---

## 📋 Complete Requirements & Setup

### Requirements

```txt
uagents==0.24.0
uagents-core==0.4.4
openai==2.30.0
httpx==0.28.1
pydantic==2.12.5
python-dotenv==1.2.2
fastmcp==3.2.0
```

### Environment Variables

```env
TMDB_API_KEY=your_tmdb_api_key_here        # from themoviedb.org (free)
ASI_ONE_API_KEY=your_asi1_key_here         # from asi1.ai
AGENT_SEED=your-agent-seed-string          # any string, keep stable
AGENT_PORT=8001                            # local dev port
```

### Setup

```bash
# 1. Clone and install
git clone https://github.com/your-username/tonights-pick.git
cd tonights-pick
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Set environment variables
cp .env.example .env
# Fill in TMDB_API_KEY and ASI_ONE_API_KEY

# 3. Run the agent locally
python agent/agent.py

# 4. Or run via Docker
docker compose -f docker/docker-compose.yml up --build
```

### TMDB API Key

Get a free key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api). The v3 key is used.

---

## 🎛️ MCP Server (Claude Desktop / Google ADK)

The same TMDB tools also run as a standalone FastMCP server over stdio:

```json
{
  "mcpServers": {
    "tonights-pick": {
      "command": "tonights-pick-mcp",
      "env": { "TMDB_API_KEY": "your_key" }
    }
  }
}
```

This makes all 13 TMDB tools available inside Claude Desktop — the uAgent and MCP server share the exact same tool implementations.

---

## 📚 Additional Resources

- **uAgents Framework**: [innovationlab.fetch.ai/resources/docs/agent-creation](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation)
- **Chat Protocol**: [innovationlab.fetch.ai/resources/docs/agent-communication](https://innovationlab.fetch.ai/resources/docs/agent-communication/agent-chat-protocol)
- **ASI:One Platform**: [asi1.ai](https://asi1.ai)
- **Agentverse Console**: [agentverse.ai](https://agentverse.ai)
- **TMDB API Docs**: [developers.themoviedb.org](https://developers.themoviedb.org/3)
- **FastMCP**: [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)

---

## 🎊 Conclusion

The TMDB Agent demonstrates how to build a **production-quality conversational recommendation agent** on Agentverse:

- **🤖 uAgent Framework**: ASI:One discoverability via chat protocol
- **🔌 FastMCP Tool Layer**: TMDB exposed as typed async tools, usable by both the uAgent and Claude Desktop
- **🧠 ASI:One Tool-Use Loop**: LLM drives tool selection; agent executes and formats
- **⚡ Concurrent I/O**: All watch-provider lookups fire simultaneously via `asyncio.gather`
- **💾 Persistent Session**: Rejections, watchlist, and seen titles survive across turns

**Built using uAgents, FastMCP, TMDB API, and ASI:One.**

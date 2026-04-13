# Appliance / Auto Whisperer — Right-to-Repair Agent

- **Category:** `LLM`, `Multi-Agent`, `Integration`
- **Difficulty:** Advanced

> **"That's the evaporator fan motor. A repairman will charge $250.  
> You can buy the part for $19 on Amazon and fix it yourself in 8 minutes — watch how."**

A Fetch.ai multi-agent system that turns a photo of a broken appliance or vehicle part into a complete DIY repair plan. Gemini Vision identifies the part, Bright Data scrapes the cheapest price from 6+ retailers, and YouTube Data API finds the best repair tutorial — all in parallel.

## Agent Profile

[View Agent on Agentverse](https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8001&address=agent1qv5c0vjykr5j3qd0rl9qx423jdy7tz92ph2dr4l0stalgm20er2usfew9cc)

---

## Architecture

```
ASI:One / Agentverse
       │  ChatMessage (photo + appliance/vehicle model string)
       ▼
┌──────────────────────────────────────────────────────────┐
│  repair-orchestrator  (port 8001, mailbox, PUBLIC)       │
│                                                          │
│  1. ACK + progress message to user                       │
│  2. Vision LLM  ← Gemini Flash via OpenAI SDK           │
│     → part_name, part_number, brand, model_number,       │
│       appliance_type, labor_cost, confidence             │
│                                                          │
│  3. REST fan-out (asyncio.gather, true parallel):        │
│       POST /diagnose-parts → parts-agent (port 8002)    │
│             Bright Data Web Unlocker · 6+ retailers      │
│       POST /find-tutorial  → tutorial-agent (port 8003)  │
│             YouTube Data API v3                          │
│                                                          │
│  4. Format hero Markdown (savings, buy link, tutorial)   │
│  5. Reply → EndSessionContent closes ASI:One session     │
└──────────────────────────────────────────────────────────┘
```

**Worker communication:** The orchestrator calls worker REST endpoints directly via `aiohttp POST` — both in true parallel via `asyncio.gather()`. This avoids a mailbox-poll deadlock inherent in `send_and_receive` when the orchestrator is in mailbox mode.

**Worker fallback:** if `parts-agent` or `tutorial-agent` are unreachable, the orchestrator calls the service functions directly and responds anyway — the agent is always available.

**SDK:** OpenAI Python SDK only. Gemini is accessed via its [OpenAI-compatible endpoint](https://ai.google.dev/gemini-api/docs/openai). No Google ADK, no Anthropic.

---

## Project Structure

```
appliance-auto-whisperer/
├── diagnostic_bureau.py          ← Orchestrator entry point
├── workers/
│   ├── parts_agent.py            ← Bright Data price scraper agent (port 8002)
│   └── tutorial_agent.py         ← YouTube tutorial search agent (port 8003)
├── app/
│   ├── config/settings.py        ← Pydantic Settings (reads .env)
│   ├── services/
│   │   ├── openai/vision_part_extractor.py   ← Gemini/GPT-4o vision → JSON
│   │   ├── brightdata/part_price_service.py  ← Web Unlocker proxy scraper
│   │   └── youtube/instructor_service.py     ← YouTube Data API v3 ranking
│   └── uagents_protocol/
│       ├── schemas.py            ← PartsSourcingRequest/Response, TutorialSearch*
│       ├── chat_inbound.py       ← Parse ChatMessage → context_text + image_b64
│       └── final_markdown.py     ← Build hero Markdown response
├── docker-compose.yml            ← Multi-container deployment (bureau / rest profiles)
├── docker-entrypoint.sh          ← Single-container startup (all 3 agents in one dyno)
├── Dockerfile.bureau             ← Docker image for bureau services
├── Dockerfile                    ← Docker image for REST API
├── render.yaml                   ← Render.com service definition
├── .env.example                  ← Copy → .env and fill in keys
└── requirements.txt
```

---

## Quick Start (Local)

### 1. Prerequisites

Python 3.11+ from [python.org](https://python.org) (not MSYS/Anaconda — prebuilt wheels needed on Windows).

### 2. Install dependencies

```powershell
cd appliance-auto-whisperer
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

### 3. Configure `.env`

```powershell
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

Fill in at minimum:

| Variable | Where to get it |
|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — free tier, 1 500 req/day |
| `YOUTUBE_API_KEY` | Google Cloud Console → Enable **YouTube Data API v3** → Create key |
| `BRIGHTDATA_CUSTOMER_ID` | [brightdata.com](https://brightdata.com) → Zones dashboard |
| `BRIGHTDATA_API_TOKEN` | Same dashboard |
| `BRIGHTDATA_ZONE` | Zone name, e.g. `web_unlocker1` |
| `AGENTVERSE_API_KEY` | [agentverse.ai](https://agentverse.ai) → Account → API Keys |
| `ORCHESTRATOR_AGENT_SEED` | Any random string, or `python -c "import secrets; print(secrets.token_hex(32))"` |
| `PARTS_AGENT_SEED` | Same |
| `TUTORIAL_AGENT_SEED` | Same |

> `OPENAI_API_KEY` is only needed if you set `VISION_PROVIDER=openai`. Gemini is the default and is free.

### 4. Run — 3 terminals, start workers first

**Terminal 1 — Parts-Sourcing Worker (port 8002)**
```powershell
python workers/parts_agent.py
```
Expected: `Parts-Sourcing Agent ready` + `REST (orch): POST http://127.0.0.1:8002/diagnose-parts`

**Terminal 2 — Tutorial Worker (port 8003)**
```powershell
python workers/tutorial_agent.py
```
Expected: `Tutorial Agent ready` + `REST (orch): POST http://127.0.0.1:8003/find-tutorial`

**Terminal 3 — Orchestrator / ASI:One gateway (port 8001)**
```powershell
python diagnostic_bureau.py
```
Expected (after ~5 s):
```
============================================================
Appliance / Auto Whisperer  —  Orchestrator
============================================================
Network    : testnet
Mailbox    : enabled
Address    : agent1q...

Workers (start BEFORE this agent):
  parts-agent    REST=http://127.0.0.1:8002/diagnose-parts
  tutorial-agent REST=http://127.0.0.1:8003/find-tutorial

Worker timeout : 120s (set WORKER_TIMEOUT_S to adjust)
Fallback       : direct service calls if workers are unreachable
============================================================
```

> **Or use the launcher:** `python run.py` starts all three agents in subprocesses with staggered startup.

---

## Register with Agentverse

1. Go to [agentverse.ai](https://agentverse.ai) → **My Agents** → **Register External Agent**.
2. Paste the `repair-orchestrator` address printed at startup.
3. Give it a name and description (e.g. *Appliance Auto Whisperer*).
4. The Chat Protocol manifest is published automatically — no extra steps.
5. In **ASI:One**, search for the agent name to start chatting.

---

## Test via ASI:One

1. Open [ASI:One](https://asi1.ai) and start a chat with **Appliance Auto Whisperer**.
2. Attach a photo of the broken part.
3. Type the appliance or vehicle model: e.g. `Whirlpool WRF560SEYM05`.
4. Hit send — you'll receive:
   - Immediate ACK
   - A "Analysing…" progress message
   - The full hero response (diagnosis, cost breakdown, buy links, tutorial)

When the REST fan-out is working you'll see on the **orchestrator terminal**:
```
[orch] REST fan-out → parts=http://127.0.0.1:8002/diagnose-parts | tutorial=http://127.0.0.1:8003/find-tutorial | timeout=120s
[orch] ← workers: parts=$42.98 at amazon.com | tutorial='GE refrigerator fan replacement...'
```

### Example response

```markdown
### 🔍 Diagnostic Complete

**Identified Part:** Evaporator Fan Motor
**Part Number:** `W10312696`

> Fan motor has seized — fridge not cooling.

*Confidence: 🟢 95% confident*

---

### 💰 Cost Breakdown

|  |  |
| :--- | ---: |
| Repairman estimate | **$250.00** |
| Best DIY part cost (amazon.com) | **$19.98** |
| **Total savings** | **+$230.02** |

🏆 **Best price: $19.98** at **amazon.com** — **[→ Buy Now](https://amazon.com/...)**

---

### 🛒 Buy the Part — All Sources Found

| # | Store | Price | Stock | Link |
| :- | :---- | ----: | :---- | :--- |
| 1 ⭐ BEST | amazon.com | **$19.98** | In Stock | [→ Buy](...) |
| 2 | repairclinic.com | $34.99 | In Stock | [→ Buy](...) |
| 3 | ebay.com | $22.50 | Check Vendor | [→ Buy](...) |

---

### 🎬 How to Fix It Yourself

**[Why Isn't Your Fridge Cold? Check Your Evaporator Fan!](https://youtube.com/...)**  · 19s

---
*You've got this! 🛠️*
```

---

## Deploy with Docker (local)

Copy `.env.example` → `.env`, then choose a mode:

**Mode A — Full 3-agent bureau (recommended)**
```bash
docker-compose --profile bureau up --build
# or: make docker-up
```
Starts `parts-agent` (8002) + `tutorial-agent` (8003) + `orchestrator` (8001).
Orchestrator waits for both worker healthchecks before starting.

**Mode B — REST API only**
```bash
docker-compose --profile rest up --build
# or: make docker-up-rest
```
REST at `http://localhost:8000`.

**Mode C — Single container (Render-style)**
```bash
docker build -f Dockerfile.bureau -t whisperer-bureau .
docker run --env-file .env -e PORT=8001 -p 8001:8001 \
  --entrypoint /app/docker-entrypoint.sh whisperer-bureau
```
`docker-entrypoint.sh` starts all 3 processes, waits `WORKER_READY_WAIT` seconds (default 8) for workers to register, then starts the orchestrator.

---

## Deploy to Render (mailbox mode)

1. Push this repo to GitHub.
2. Render dashboard → **New → Web Service → Docker** → select the repo, set `Dockerfile Path` to `./Dockerfile.bureau`.
3. Add secrets from `.env` in the Render environment panel. Leave `AGENT_ENDPOINT` **blank** (mailbox mode).
4. Deploy — Render injects `PORT`; the orchestrator reads it automatically.
5. Copy the `repair-orchestrator` address from Render logs and register it in Agentverse.

---

## Troubleshooting

### Port already in use (`[Errno 10048]` on Windows)

```powershell
$p = (Get-NetTCPConnection -LocalPort 8001 -State Listen -EA SilentlyContinue).OwningProcess
if ($p) { Stop-Process -Id $p -Force; "Killed PID $p" } else { "Port free" }
```
The orchestrator also auto-kills stale processes on startup via `psutil` (install with `pip install psutil`).

### Workers show no log activity / orchestrator falls back to direct calls

The orchestrator POSTs directly to worker REST endpoints (`/diagnose-parts`, `/find-tutorial`). Workers must be running and reachable on their ports.

**Fix**: Start workers **before** the orchestrator. Verify endpoints in the orchestrator's startup log. In Docker, ensure `PARTS_AGENT_HOST` and `TUTORIAL_AGENT_HOST` are set to the Compose service names.

You should see this on the parts-agent terminal when a message arrives:
```
[parts] Request received: part=Evaporator Fan Motor (WR60X26866) brand=GE model=PYE22KBLCTS
[parts] Done — $42.98 at amazon.com (6 sources)
```

### `jiter` build failure on Windows

Use Python from **python.org** (not MSYS/Conda), or build inside Docker.

### Bright Data returns no prices

Check `BRIGHTDATA_CUSTOMER_ID`, `BRIGHTDATA_API_TOKEN`, and `BRIGHTDATA_ZONE`. Zone type must be **Web Unlocker**. PartSelect requires a premium access upgrade (separate from the base zone).

### YouTube returns a placeholder link

Set `YOUTUBE_API_KEY` and enable **YouTube Data API v3** in Google Cloud Console.

### Gemini returns 503

Transient — the OpenAI client retries automatically (you'll see `Retrying request` in logs). If it persists, check your `GEMINI_API_KEY` quota at [aistudio.google.com](https://aistudio.google.com).

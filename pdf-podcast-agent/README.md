# PDF-to-Podcast Agent

Turn any research PDF into a 2-host debate podcast with live Q&A, interactive debates, and Stripe-gated premium features — all inside ASI:One.

- **Category:** `Multi-Agent`, `LLM`, `Payments`, `RAG`
- **Difficulty:** Advanced
- **Tech stack:** Python, uAgents, ASI:One, OpenAI TTS, Stripe, pydub, pdfplumber

## Overview

Reading dense research papers causes serious fatigue. This agent replicates the "NotebookLM" podcast experience: upload a PDF, get back an MP3 debate between two AI hosts — a Skeptic and an Expert. After the podcast, the hosts stay in chat for live Q&A and can run a turn-by-turn live debate, gated by a $10 Stripe payment via the AgentPaymentProtocol.

## Features

- ✅ PDF text extraction with pdfplumber
- ✅ RAG-style key insight extraction (core thesis, metrics, controversy)
- ✅ AI-generated debate script (10–14 lines) between a Skeptic and an Expert
- ✅ Parallel TTS voice synthesis with pydub audio stitching → MP3
- ✅ DOCX transcript with extended director's cut
- ✅ Free live Q&A — tag @skeptic-agent or @expert-agent in chat
- ✅ Paid live debate — 8-turn agent-to-agent debate streamed in chat
- ✅ Host personality customization — 16 combos across 4 presets
- ✅ Stripe payment gate ($10) via AgentPaymentProtocol (embedded checkout)
- ✅ Docker Compose deployment for all 6 agents

## Prerequisites

- Python 3.10+
- ffmpeg on PATH (`winget install ffmpeg` · `brew install ffmpeg` · `apt install ffmpeg`)
- ASI:One API key — [asi1.ai](https://asi1.ai)
- OpenAI API key (TTS only) — [platform.openai.com](https://platform.openai.com)
- Agentverse API key — [agentverse.ai](https://agentverse.ai)
- Stripe API keys (optional) — [dashboard.stripe.com](https://dashboard.stripe.com/apikeys)

## Installation

```bash
cd innovation-lab-examples/pdf-podcast-agent

python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .\.venv\Scripts\Activate.ps1   # Windows

pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file using `.env.example`:

```bash
cp .env.example .env
```

Then run `python get_addresses.py` and paste the printed addresses into `.env`.
If you use Docker Compose, address variables are auto-generated from seeds at container startup.

### Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ASI1_API_KEY` | Yes | ASI:One LLM — all text generation |
| `OPENAI_API_KEY` | Yes | OpenAI TTS — audio synthesis only |
| `AGENTVERSE_API_KEY` | Yes | Agent registration and mailbox |
| `EXTRACTOR_ADDRESS` | Yes | From `get_addresses.py` |
| `SCRIPTWRITER_ADDRESS` | Yes | From `get_addresses.py` |
| `VOICE_STUDIO_ADDRESS` | Yes | From `get_addresses.py` |
| `HOST_A_ADDRESS` | Yes | From `get_addresses.py` |
| `HOST_B_ADDRESS` | Yes | From `get_addresses.py` |
| `STRIPE_SECRET_KEY` | No | Enables Stripe payment gate |
| `STRIPE_PUBLISHABLE_KEY` | No | For embedded Stripe checkout |

## Run the Agent

Start all 6 agents (sub-agents first, orchestrator last):

```bash
python extractor_agent.py       # Terminal 1
python scriptwriter_agent.py    # Terminal 2
python voice_studio_agent.py    # Terminal 3
python host_a_agent.py          # Terminal 4
python host_b_agent.py          # Terminal 5
python orchestrator.py          # Terminal 6 (start last)
```

Or use the convenience launcher:

```bash
python run.py
```

Or use Docker:

```bash
cp .env.example .env
# Fill in your API keys
docker-compose up --build -d
docker-compose logs -f
```

Docker Compose now auto-resolves `EXTRACTOR_ADDRESS`, `SCRIPTWRITER_ADDRESS`,
`VOICE_STUDIO_ADDRESS`, `HOST_A_ADDRESS`, and `HOST_B_ADDRESS` if they are left
blank in `.env`, using deterministic seeds (`*_SEED` values).

## Expected Output

After starting, the orchestrator prints:

```
INFO: [pdf_podcast_orchestrator]: Starting agent with address: agent1q...
INFO: [pdf_podcast_orchestrator]: Agent inspector available at https://agentverse.ai/inspect/?uri=...
INFO: [pdf_podcast_orchestrator]: [Orchestrator] sub-agents wired:
  Extractor    agent1q...
  Scriptwriter agent1q...
  Voice Studio agent1q...
  Host A       agent1q...
  Host B       agent1q...
```

When a user uploads a PDF via ASI:One, the agent replies with:

- Episode title and duration
- MP3 download link
- DOCX transcript link
- Script preview (core argument, metrics, controversy)
- Live Q&A prompt (free) and Live Show Pass ($10)

## Demo

![ASI:One Demo](./assets/demo.png)

## Architecture

```text
User uploads PDF to ASI:One
        │
        ▼
  ┌─────────────┐    ExtractRequest     ┌──────────────┐
  │ Orchestrator │──────────────────────▶│ RAG Extractor│
  │  (port 8000) │◀─ ResearchInsights ──│  (port 8001) │
  │              │                      └──────────────┘
  │              │    PodcastScript      ┌──────────────┐
  │              │──────────────────────▶│ Scriptwriter │
  │              │◀─ PodcastScript ─────│  (port 8002) │
  │              │                      └──────────────┘
  │              │    PodcastScript      ┌──────────────┐
  │              │──────────────────────▶│ Voice Studio │
  │              │◀─ AudioResponse ─────│  (port 8003) │
  │              │                      └──────────────┘
  │              │   ContextInjection    ┌──────────────┐
  │              │─────────────────────▶│ Host A       │
  │              │   DebateTurn          │ "Skeptic"    │
  │              │─────────────────────▶│  (port 8004) │
  │              │                      └──────────────┘
  │              │   ContextInjection    ┌──────────────┐
  │              │─────────────────────▶│ Host B       │
  │              │   DebateTurn          │ "Expert"     │
  │              │─────────────────────▶│  (port 8005) │
  └─────────────┘                      └──────────────┘
```

### Payment flow

1. User types **"debate"** or **"customize"** in chat
2. Orchestrator sends `RequestPayment` with embedded Stripe Checkout (`ui_mode="embedded_page"`)
3. User completes payment in the Stripe overlay
4. ASI:One sends `CommitPayment` → Orchestrator verifies → sends `CompletePayment`
5. User types **"continue debate"** to start the live show

## Project Structure

```text
pdf-podcast-agent/
├── orchestrator.py        # Main agent — chat protocol, payment, debate relay
├── extractor_agent.py     # Agent 1: RAG extraction (port 8001)
├── scriptwriter_agent.py  # Agent 2: Debate script generation (port 8002)
├── voice_studio_agent.py  # Agent 3: TTS + audio stitching (port 8003)
├── host_a_agent.py        # Host A: The Skeptic — Q&A + debate (port 8004)
├── host_b_agent.py        # Host B: The Expert — Q&A + debate (port 8005)
├── schemas.py             # Pydantic models (typed contracts between agents)
├── get_addresses.py       # Prints agent addresses (run first)
├── run.py                 # Convenience launcher (all 6 agents)
├── test_pipeline.py       # Local smoke test
├── requirements.txt
├── .env.example
├── Dockerfile             # Python 3.12 + ffmpeg
├── docker-compose.yml     # 6-container deployment
├── render.yaml            # Render.com deployment config
└── output/                # Generated MP3/DOCX files (gitignored)
```

## Troubleshooting

- **"Missing ASI1_API_KEY / OPENAI_API_KEY"** — Check `.env` is created from `.env.example` with real values.
- **"I do not have enough funds to register on Almanac contract"** — Safe to ignore for local dev.
- **Port already in use** — Kill stale process on that port and restart.
- **Docker build fails with audioop-lts** — Expected on Python <3.13; the marker in `requirements.txt` handles this.
- **Debate hosts repeat arguments** — Full debate history is passed via `debate_history` field with anti-repetition prompts.

## Resources

- [Innovation Lab Docs](https://innovationlab.fetch.ai/resources/docs/intro)
- [Agentverse](https://agentverse.ai/)
- [ASI:One API](https://asi1.ai/)
- [uAgents Framework](https://github.com/fetchai/uAgents)
- [Agent Payment Protocol](https://innovationlab.fetch.ai/resources/docs/payments)
- [Stripe Sandboxes](https://docs.stripe.com/sandboxes)

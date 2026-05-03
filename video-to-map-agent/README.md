# Video Map Agent

> Turn YouTube travel vlogs into a fully planned, day-by-day trip itinerary — with a route map, place photos, weather monitoring, PDF guide, and Excel workbook — all in one multi-agent workflow.

- **Category:** `Multi-Agent`, `Payments`, `LLM`, `Integration`
- **Difficulty:** 🔴 Advanced
- **Tech stack:** Python, Fetch.ai uAgents, ASI:One, Agentverse, Google Maps API, Google Places API, YouTube Data API, Stripe, ReportLab, openpyxl

---

## Overview

Planning a trip from travel videos is tedious. You watch several vlogs, try to remember which locations each creator visited, piece together a route, and end up with a scattered list of bookmarks and no actual plan.

Video Map Agent solves this end-to-end. You paste YouTube travel video URLs into the ASI:One chat. A network of autonomous agents transcribes each video, extracts every location mentioned, validates and scores the stops across all videos, curates a day-by-day route, and delivers a complete trip package — all within the conversation.

---

## Features

- **Multi-video consensus scoring** — stops mentioned across multiple videos are ranked higher, surfacing the places every creator independently visited
- **Day-by-day itinerary** — structured per-day plan with themes, activities, estimated costs, and restaurant suggestions
- **Google Places photos** — real photos of each stop embedded inline in the chat
- **Route map preview** — static Google Maps PNG with numbered markers and a driving polyline, attached as a native image
- **Interactive Google Maps link** — one-click driving directions for the full route
- **Daily weather monitoring** — a background agent checks weather at every stop each day until your trip date
- **PDF travel guide** — downloadable full itinerary with maps URL and trip details
- **Excel planning workbook** — itinerary, restaurants, budget, weather log, and maps in one spreadsheet
- **Stripe payment gate** — $2.99 per curated trip plan, processed entirely within the chat (disable in dev mode by leaving `STRIPE_SECRET_KEY` blank)

---

## Architecture

The system is composed of **9 autonomous agents** communicating over the Fetch.ai uAgents protocol:

```
User (ASI:One chat)
        │
        ▼
┌─────────────────────┐
│  Orchestrator Agent │  ◄── coordinates the full pipeline
└────────┬────────────┘
         │
    ┌────┼────────────────────────────────────────────┐
    ▼    ▼                                            ▼
Transcript  Location          Aggregator         Trip Planner
  Agent     Extractor  ──►   Agent (dedup +    Agent (curates
(YouTube)   Agent             score stops)      day-by-day
                                                 route)
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
         Weather              PDF Generator      Excel Generator
         Monitor               Agent               Agent
          Agent
```

| Agent | File | Responsibility |
|---|---|---|
| Orchestrator | `orchestrator_agent.py` | User interaction, pipeline control, Stripe payment, final response assembly |
| Transcript | `transcript_agent.py` | Fetches YouTube transcript via YouTube Data API |
| Location Extractor | `location_extractor_agent.py` | Uses ASI:One to parse place names from transcript text |
| Geocoder/Mapper | `geocoder_mapper_agent.py` | Validates places via Google Places Text Search |
| Aggregator | `aggregator_agent.py` | Deduplicates stops across videos, scores by frequency + rating |
| Trip Planner | `trip_planner_agent.py` | Uses ASI:One to build a day-by-day route with activities and budget |
| Weather Monitor | `weather_monitor_agent.py` | Runs daily weather checks on all stops until the trip date |
| PDF Generator | `pdf_generator_agent.py` | Generates a PDF travel guide with ReportLab |
| Excel Generator | `excel_generator_agent.py` | Generates an Excel workbook with openpyxl |

---

## Prerequisites

- Python 3.10+
- API keys for: ASI:One, Google Maps/Places, YouTube Data API, Agentverse
- Stripe test keys (optional — leave blank to skip payment gate)

---

## Installation

```bash
git clone https://github.com/stripathy1999/Video-Map-Agent-.git
cd Video-Map-Agent-

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Environment Variables

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

| Variable | Required | Description |
|---|---|---|
| `ASI1_API_KEY` | Yes | ASI:One LLM API key — [get one at asi1.ai](https://asi1.ai) |
| `GOOGLE_MAPS_API_KEY` | Yes | Enables geocoding, Static Maps, and Places Photos |
| `YOUTUBE_API_KEY` | Yes | YouTube Data API for transcript fetching |
| `AGENTVERSE_API_KEY` | Yes | Fetch.ai Agentverse key for agent registration and file storage |
| `STRIPE_SECRET_KEY` | No | Stripe test key — leave blank to disable the $2.99 payment gate |
| `*_SEED` | Yes | Unique seed strings that derive each agent's stable address |
| `*_AGENT_ADDR` | Yes* | Filled in after first run (each agent prints its address on startup) |

---

## Running the Agents

Each agent is a standalone process. Open a separate terminal for each:

```bash
# Terminal 1
python orchestrator_agent.py

# Terminal 2
python transcript_agent.py

# Terminal 3
python location_extractor_agent.py

# Terminal 4
python geocoder_mapper_agent.py

# Terminal 5
python aggregator_agent.py

# Terminal 6
python trip_planner_agent.py

# Terminal 7
python weather_monitor_agent.py

# Terminal 8
python pdf_generator_agent.py

# Terminal 9
python excel_generator_agent.py
```

On first run, each agent prints its address:
```
INFO: [transcript_agent]: Starting agent with address: agent1q...
```

Copy each address into the corresponding `*_AGENT_ADDR` variable in `.env`, then restart the orchestrator.

---

## Usage

1. Open [ASI:One chat](https://asi1.ai)
2. Find or search for `travel_map_orchestrator` (or `@video-map-agent`)
3. Paste 1–3 YouTube travel video URLs, optionally with budget and trip length:

```
https://youtube.com/watch?v=XXXX https://youtube.com/watch?v=YYYY budget $1200 for 7 days
```

4. Complete the $2.99 Stripe payment (or skip if `STRIPE_SECRET_KEY` is blank)
5. The agent returns:
   - Cross-video consensus stops with inline place photos
   - Day-by-day itinerary with activities and costs
   - Route map preview (attached image)
   - Daily weather monitoring until your trip date
   - Downloadable PDF travel guide
   - Downloadable Excel planning workbook

---

## Expected Output

```
## Your Southern California road trip is ready to go

This seven-day itinerary blends coastal vibes, desert adventures, and Hollywood glamour...

## Stops that appeared in multiple videos
- [photo] La Jolla Cove — mentioned in 3 of 3 videos — 4.8★
- [photo] Joshua Tree National Park — mentioned in 3 of 3 videos — 4.8★
...

## Your day-by-day plan
### Day 1 — San Diego Arrival (~$120)
- [photo] La Jolla Cove — seal watching and coastal hiking
...

## Your trip package
- Route map: [open interactive Google Maps directions](...)
- PDF travel guide: download itinerary_20260428_XXXXXX.pdf
- Excel planning workbook: download itinerary_20260428_XXXXXX.xlsx
```

---

## Demo

![Video Map Agent Demo](./assets/demo.png)

---

## Agent Profile

[View Orchestrator on Agentverse](https://agentverse.ai/agents/agent1qvnh3yr9hgtqs58jcffnqfvu27xvh8ums7f096e03s7takn0fxpdqn88hft)

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Aggregator timed out` | Ensure `aggregator_agent.py` is running and `AGGREGATOR_AGENT_ADDR` is set correctly in `.env` |
| `Static Maps returned non-PNG payload` | Your Google Maps API key may need the Static Maps API enabled in Google Cloud Console |
| `ExternalStorage upload failed` | Transient Agentverse outage — the agent retries once automatically and falls back to a base64 inline image |
| `No locations extracted` | The video may not have a transcript available; try a different video |
| Stripe checkout not appearing | Set `STRIPE_SECRET_KEY` in `.env` — leave it blank to skip payment in dev mode |

---

## License

Apache 2.0

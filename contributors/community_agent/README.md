# Community Growth Agent

![uAgents](https://img.shields.io/badge/uAgents-mailbox--enabled-blue)
![Events](https://img.shields.io/badge/events-conferences%20%26%20hackathons-green)
![Web search](https://img.shields.io/badge/web%20search-Tavily-orange)
![Read-only](https://img.shields.io/badge/read--only-no%20sensitive%20data-lightgrey)
![Python](https://img.shields.io/badge/python-3.10+-blue)

An AI assistant that helps **event organizers** plan and grow meetups, conferences, community events, and hackathons — locally or globally. Ask in plain language; it suggests speakers, venues, sponsor emails, social posts, and more. It never sends emails or posts for you — it only gives drafts and suggestions.

---

## What it does

- **Engagement** — Review past events and get short recommendations.
- **Predictions** — Rough RSVP ranges, timing, and venue size for upcoming events.
- **Speakers** — Suggestions with LinkedIn profiles and how to contact them (when available).
- **Sponsors** — Ready-to-use email drafts for different sponsor types.
- **Social posts** — Variants for LinkedIn, X, WhatsApp, Instagram, event pages.
- **Venues** — Venue ideas with address, capacity, contact, and speaker-session fit when possible.

---

## Example queries

| You might ask… |
|----------------|
| *Suggest 5 speakers for a DevOps meetup in Bangalore; include LinkedIn if you can.* |
| *Find venues in Mumbai for a 80-person hackathon next month.* |
| *I need sponsor email drafts for a community conference — local startup, mid-size, enterprise.* |
| *Generate 5 social post variants for our AI meetup, tone: professional.* |
| *We had 3 past events: [paste your list]. What should we improve?* |
| *Predict RSVP and no-show for our upcoming 2-day hackathon.* |
| *Who can speak at our venue speaker session on cloud security?* |
| *Suggest venues with contact or LinkedIn for a 50-person workshop in Delhi.* |

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Agent runtime | [uAgents](https://docs.fetch.ai/agents/uaagents/) (mailbox-enabled) |
| LLM | [ASI:One](https://api.asi1.ai) (OpenAI-compatible chat completions) |
| Web search | [Tavily](https://tavily.com) (advanced search context) |
| HTTP client | `httpx` |
| Language | Python 3.10+ |

**Flow:** User message → optional Tavily search (for speaker/venue/LinkedIn-style queries) → context injected into prompt → ASI:One `asi1` model → plain-text reply. Web search is triggered by keywords (e.g. speaker, venue, LinkedIn, contact); ASI:One is called with `web_search: False` so responses stay text-only.

---

## Prerequisites

- **Python 3.10+**
- **ASI:One API key** — [ASI:One](https://api.asi1.ai) (required)
- **Tavily API key** — [Tavily](https://tavily.com) (optional; enables real web search for speakers/venues/LinkedIn)

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ASI_ONE_API_KEY` | Yes | API key for ASI:One chat completions (`https://api.asi1.ai/v1`) |
| `TAVILY_API_KEY` | No | API key for Tavily; if set, speaker/venue/contact queries use live web search |

Example (Agentverse secrets or local `.env`):

```bash
export ASI_ONE_API_KEY="your_asi_one_key"
export TAVILY_API_KEY="your_tavily_key"   # optional
```

---

## Installation & run

```bash
# Clone (or navigate to the repo)
cd "path/to/repo"

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install uagents uagents_core httpx tavily-python

# Set env vars (see above), then run the agent
python agent.py
```

Without `tavily-python` or `TAVILY_API_KEY`, the agent still runs; speaker/venue/LinkedIn queries will not use web search.

---

## Project layout

```
.
├── agent.py      # uAgent + chat protocol; Tavily search + ASI:One chat
└── README.md
```

---

## License

MIT (or your chosen license).
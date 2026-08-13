# ASI1 Conversational Property Finder (MVP)

A conversational Property Finder agent that runs on **ASI1** (https://asi1.ai). It accepts natural language search queries, extracts filters, fetches real-time listings from the **Repliers MLS API**, and returns formatted results. Supports follow-up refinements and “more” pagination.

- **No database, no dashboard, no CRM** — demo-ready MVP only.

## Project structure

```
conversational-property-finder/
├── run_agent.py            # Entry point
├── asi1_agent/
│   ├── property_agent.py   # ASI1 uAgent: chat handler, state, Repliers call
│   ├── nl_parser.py        # Extract location, price, beds, property type from text
│   ├── state_manager.py   # In-memory session filters (keyed by session ID)
│   ├── requirements.txt
│   └── .env.example
├── repliers_client/
│   ├── client.py           # search_listings(filters) -> listings + meta
│   ├── filters.py          # Our filter dict -> Repliers API params
│   └── formatter.py        # Listings -> readable chat text
└── README.md
```

## Setup

1. **Navigate** to this example:

   ```bash
   cd stripe-payment-agents/conversational-property-finder
   ```

2. **Create a virtualenv** (recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r asi1_agent/requirements.txt
   ```

4. **Configure environment**:

   ```bash
   cp asi1_agent/.env.example asi1_agent/.env
   # Edit .env: AGENT_SECRET_KEY_1 and REPLIERS_API_KEY are required.
   ```

   The agent loads `.env` from `asi1_agent/` when it runs. You can also export the
   variables in your shell instead.

## Run the agent

```bash
python3 run_agent.py
```

You should see the agent address (e.g. `agent1q...`) and Mailbox/Almanac messages. Open https://asi1.ai, find the agent by name or address, and chat.

## Usage (in ASI1 chat)

- **First message:** e.g. *“Find 2 bedroom homes under $600k in Austin.”*  
  → Agent parses location, max price, bedrooms; calls Repliers; returns top 3 listings and hints.

- **Refine:** *“refine under 550k”* or *“under 550k”*  
  → Updates `max_price`, re-queries, returns updated results.

- **Refine:** *“only condos”* or *“change to 3 bedrooms”*  
  → Updates filters and returns new results.

- **More:** *“more”*  
  → Next page (same filters), returns next 3 listings.

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `AGENT_SECRET_KEY_1` | Yes | Agent seed (identity). Same value ⇒ same agent address. |
| `AGENTVERSE_API_KEY` | Yes (for Mailbox) | API key from Agentverse; used for Mailbox/Almanac. |
| `REPLIERS_API_KEY` | Yes | Repliers API key for `https://api.repliers.io/listings`. |
| `USE_MAILBOX` | No (default: true) | Use Mailbox so ASI1 can deliver messages without a public URL. |
| `AGENT_PORT` | No (default: 8000) | Local agent port. |
| `EMAIL_API_KEY` | No (for emailing wishlist) | Resend API key (`re_...`) used to send wishlist emails. |
| `EMAIL_TO` | No | Optional default email recipient for wishlist export (users can also type an email in chat). |

### Wishlist export to email

If `EMAIL_API_KEY` is set (Resend) the user can email their wishlist by saying:

- `export wishlist to you@example.com`

If `EMAIL_TO` is set, users can also say just `export wishlist` and it will use the default recipient.

## Which cities/searches work?

Listings depend on your **Repliers API / MLS coverage**. If a city returns no results (e.g. San Jose), that area may not be in the MLS your account uses. Try cities/states that are included in your Repliers subscription (e.g. Austin, TX works in many setups). The agent will suggest broadening the search or trying a different area when no listings are found.

## Success criteria (MVP)

- User: *“2 bed under 600k in Austin”* → agent returns 3 listings.
- User: *“under 550k”* → agent returns updated listings.
- User: *“more”* → agent returns next page.

## Constraints (not in scope)

No CMA, mortgage calculator, map, login, persistence, multi-agent, analytics, email, or voice. MVP only.

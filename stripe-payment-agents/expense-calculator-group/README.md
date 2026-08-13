# Receipt / Expense Calculator Agent

Agent for **ASI-One** and **Agentverse** that splits receipts fairly: send a **photo of a receipt** (or add items manually), then have each person mark which items they brought and see the split.

## Run locally

```bash
cd expense-calculator-group
python -m venv venv
source venv/bin/activate   # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, AGENT_SEED, AGENT_MAILBOX_KEY
python agent.py
```

## Run with Docker

1. **Create `.env`** (required for mailbox + receipt extraction):
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set at least: `OPENAI_API_KEY`, `AGENT_SEED`, `AGENT_MAILBOX_KEY`. Optionally add Stripe keys.

2. **Build and run with Docker Compose:**
   ```bash
   cd expense-calculator-group
   docker compose build
   docker compose up -d
   ```
   The agent listens on **port 8004**. Logs: `docker compose logs -f`.

3. **Or run the image directly:**
   ```bash
   docker build -t expense-calculator-agent .
   docker run --env-file .env -p 8004:8004 expense-calculator-agent
   ```

4. **Connect to Agentverse:** Use the Inspector/connect URL from Agentverse and point it at your host (e.g. `http://<your-host>:8004`). If running locally, use the link printed in the agent logs after you open the Inspector.

5. **Stop:**
   ```bash
   docker compose down
   ```

## Deploy on Agentverse + ASI-One

1. **Agentverse:** [agentverse.ai](https://agentverse.ai) → Agents → Launch an Agent → **Chat Protocol**.
2. Use **mailbox** (no public URL needed): run the agent (e.g. on your machine or a server) and connect via the Agent Inspector link from the logs.
3. **ASI-One:** After the agent is registered on Agentverse, it appears in [asi1.ai](https://asi1.ai); you can chat there or add it to a group.

See [deploy-agent-on-av/docs.md](../../deploy-agent-on-av/docs.md) for Render/mailbox deployment and env vars.

## What the agent does

- **Receipt photo:** Attach an image → agent extracts line items (name + price) with OpenAI Vision and lists them.
- **Optional Stripe payment:** If `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY` are set, after listing items the agent sends a **Stripe payment request** (embedded Checkout, same as [stripe-horoscope-agent](../../stripe-horoscope-agent)). Complete payment in the UI, then say **done** to start the poll.
- **Manual:** Say **new receipt**, then **add Pizza 12** (and more). Say **done** when finished.
- **Poll:** Each person replies with the **numbers** of items they brought (e.g. `1,2,3`). Multiple people can claim the same item.
- **Split:** Say **calculate** → agent shows each person’s share (only people who brought an item pay for it).

## Commands

| Command | Description |
|--------|-------------|
| *(photo)* | Extract items from receipt image |
| `new receipt` | Start a new receipt |
| `add <name> <price>` | Add item (e.g. `add Coffee 3.50`) |
| `done` | Lock items and start the poll |
| `1,2,3` | Your items (reply with numbers) |
| `calculate` | Show split per person |
| `I'm Alice` | Set display name |
| `help` | Show instructions |

## Env vars

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes (for photos) | OpenAI API key for receipt image extraction (Vision) |
| `AGENT_SEED` | Yes | Seed phrase for agent identity |
| `AGENT_MAILBOX_KEY` | Yes (for Agentverse) | Mailbox key from Agentverse |
| `AGENTVERSE_URL` | No | Default `https://agentverse.ai` |
| `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` | No | If both set, agent requests Stripe payment after listing receipt items (like stripe-horoscope-agent) |
| `STRIPE_AMOUNT_CENTS` | No | Default `100` ($1.00) |

## Project layout

```
expense-calculator-group/
├── agent.py           # uAgents chat + payment protocols (photo, text, Stripe)
├── config.py          # Env config (Stripe optional)
├── expense_logic.py   # Receipt, split calculation
├── receipt_vision.py  # OpenAI Vision receipt extraction
├── stripe_payments.py # Stripe Checkout create/verify (same pattern as stripe-horoscope-agent)
├── payment_proto.py   # AgentPaymentProtocol seller role
├── requirements.txt
├── .env.example
└── README.md
```

# Stripe Horoscope Agent (ASI:One + AgentPaymentProtocol)

A small, production-style example agent that:

- Chats using the **AgentChatProtocol**
- Requests a **$1 USD payment via Stripe** using the **AgentPaymentProtocol** (`payment_method="stripe"`)
- After payment, generates a “horoscope of the day” using **ASI:One** (`model="asi1"`)

This example is intentionally split across small files so it’s easy to understand and reuse.

## Payment flow

1. User says something like **“give me my horoscope”**
2. Agent asks for a star sign
3. Agent sends `RequestPayment` with:
   - `accepted_funds=[Funds(currency="USD", amount="1.00", payment_method="stripe")]`
   - `metadata["stripe"]` containing an **embedded Stripe Checkout session**
4. UI/buyer sends `CommitPayment(transaction_id=<checkout_session_id>, funds.payment_method="stripe")`
5. Agent verifies Stripe Checkout Session `payment_status == "paid"`, sends `CompletePayment`, and replies with the horoscope text

## Getting keys

### ASI:One

- Create an API key from the [ASI:One developer page](https://asi1.ai/developer)
- Set it as `ASI_ONE_API_KEY`

### Stripe (test mode)

- Use a Stripe sandbox for testing (no real money moves). See [Stripe Sandboxes](https://docs.stripe.com/sandboxes?locale=en-GB).
- Get your test keys (publishable + secret). See [Stripe API keys](https://docs.stripe.com/keys?locale=en-GB).
- Copy:
  - **Secret key** (`sk_test_...`) → `STRIPE_SECRET_KEY`
  - **Publishable key** (`pk_test_...`) → `STRIPE_PUBLISHABLE_KEY`

## Setup

```bash
cd innovation-lab-examples/stripe-horoscope-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 agent.py
```

## Running + testing (Agentverse UI)

1. After you start the agent, the terminal prints an **Agent inspector** link like:
   - `https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8012&address=...`
2. Open that inspector link and start a chat with the agent.
3. In chat, send:
   - `give me my horoscope`
4. When asked, reply with a sign (e.g. `Leo`).
5. The UI will show a Stripe payment request:
   - Complete the embedded Stripe Checkout (use Stripe test card `4242 4242 4242 4242`, any future expiry, any CVC, any ZIP).
   - Then **approve** the payment in the UI (this sends `CommitPayment` to the agent).
6. The agent verifies Stripe shows the Checkout Session as **paid**, then replies with your horoscope.

## Project structure

```text
stripe-horoscope-agent/
  agent.py            # Entry point: loads env, includes chat/payment protocols
  handlers.py         # Chat + payment handlers (state machine)
  stripe_payments.py  # Stripe Checkout session create/verify
  llm.py              # ASI:One calls + prompts
  state.py            # Small state helpers (ctx.storage) + sign parsing
  config.py           # Environment variables
  chat_proto.py       # Chat protocol wrapper + ack handler
  payment_proto.py    # Payment protocol wrapper (seller role)
  requirements.txt
  .env.example
  README.md
```

## Notes

- The agent only initiates payment when the user asks for a **horoscope** (simple intent detection).
- State is short-lived and stored in `ctx.storage` to support the multi-turn flow (sign → payment → horoscope).
- If you start a brand-new chat thread and you still see an old “payment pending” prompt, say something like **“hello”** or **“what can you do?”** — the agent treats that as a fresh start and clears any old pending-payment state.

## Troubleshooting

- **`Missing ASI_ONE_API_KEY` / `Missing STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY`**
  - Make sure you copied `.env.example` → `.env` and filled in the values.
- **`I do not have enough funds to register on Almanac contract`**
  - This warning is safe to ignore for this local demo. It’s about on-chain registration; the example still runs via mailbox + Agentverse.


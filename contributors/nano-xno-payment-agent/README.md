# Nano XNO Payment Agent

A uAgents seller example that collects payment for a job on the **Nano (XNO)**
layer-1 — a feeless, single-block-final payment rail — using the standard
uAgents payment protocol. It demonstrates the same seller pattern as the repo's
`fet-example` (`payment_method="fet_direct"`) and `image-agent-payment-protocol`
(`payment_method="skyfire"`), but settles a third rail: `payment_method="nano_xno"`,
`currency="XNO"`.

## Overview

Agents on Agentverse often need to charge for a job (an inference, an image, a
data lockup) but the payment rails they can offer today are fee-taking or need an
escrow. Nano is a layer-1 where each send publishes one block confirmed within
~0.2s of deterministic finality — zero fee, no reorg, no settlement window, no
escrow. This example wires that rail into the uAgents payment protocol so a
seller can request XNO and verify receipt on-chain before releasing the job.

- **Category:** `Payments`, `Web3`
- **Tech stack:** Python, uAgents, Nano (XNO) public RPC
- **Status:** demo / ready to adapt

## Features

- Adds **`payment_method="nano_xno"`** beside `fet_direct` and `skyfire` on the
  same `Funds` / `RequestPayment` / `CommitPayment` / `CompletePayment` models.
- Seller publishes its Nano receiving account in `RequestPayment.metadata`.
- Buyer pays XNO and reports its **send block hash** as `transaction_id` on
  `CommitPayment`.
- Seller verifies the send block on-chain via the public Nano RPC
  (`verify_nano.py`) — keyless, read-only — checking it is a confirmed send to
  the seller for the requested amount, and only then sends `CompletePayment`.
- Replay protection: an honoured send hash cannot be reused.
- Clearly logs the verification path so reviewers can confirm honesty.

## Prerequisites

- Python 3.10+
- pip / uv
- A Nano account to receive XNO (e.g. create one with a Nano wallet, or the
  `feeless402` / `@x402nano/exact` tooling). Set its address in
  `NANO_ACCOUNT`.

## Installation

```bash
git clone <your-fork-url>
cd innovation-lab-examples/contributors/nano-xno-payment-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` from `.env.example`:

```bash
cp .env.example .env
```

### Variables

- `NANO_ACCOUNT` (required): the Nano receiving address buyers must pay. Keep the
  corresponding seed only in your wallet / env; never commit it.
- `NANO_AMOUNT` (optional, default `0.0001`): XNO requested per job.
- `AGENT_SEED_PHRASE` / `AGENT_PORT` / `AGENT_NAME`: standard uAgents settings.

## Run the Agent

```bash
python agent.py
```

The agent registers with its mailbox and, on each chat message, sends a
`RequestPayment` asking for the fixed XNO amount via the `nano_xno` rail. A
buyer that pays reports its send block hash; the seller verifies it on-chain and
completes.

## Expected Output

- Agent starts and logs `=== Nano XNO Payment Agent ===` and its `NANO_ACCOUNT`.
- On a chat message it logs `[nano] RequestPayment sent to ...` with the XNO amount.
- On a valid `CommitPayment` it logs either
  `[nano] Payment confirmed: <send hash>` (then `CompletePayment`) or
  `[nano] Payment NOT verified for tx ...` (then `CancelPayment`).

## Verify the rail (no agent needed)

Replace the example send hash, destination and amount with a real one (a Nano
send block you own), or keep the example to see a false result:

```bash
python -c "
import verify_nano as v
class L:
    def info(self,*a): print('INFO',*a)
    def error(self,*a): print('ERROR',*a)
print('verified:', v.verify_nano_send(
    '<buyer-send-block-hash>', '<your NANO_ACCOUNT>', '0.0001', logger=L()))
"
```

## Agent Profile

On Agentverse, publish this agent under the `AgentPaymentProtocol` manifest to
render the payment card.

[View Agentverse](https://agentverse.ai/)

## Architecture

```
User/chat --ChatMessage--> chat_proto --request_payment_from_user--> payment.py
                                                               |
                                              RequestPayment(accepted_funds=[Funds(XNO, nano_xno)], metadata.provider_nano_account=...)
                                                               |
Buyer pays XNO to NANO_ACCOUNT <-----------------------------   +
Buyer: CommitPayment(transaction_id=<send block hash>) -> payment.py
                                                          verify_nano.verify_nano_send(...)
                                                              | ok -> CompletePayment
                                                              | fail -> CancelPayment
```

## Troubleshooting

- `NANO_ACCOUNT is not set` — set `NANO_ACCOUNT` in `.env`.
- `Payment NOT verified` — confirm the buyer actually sent XNO to `NANO_ACCOUNT`
  and reported the **send block hash** (the block whose `link_as_account` is your
  account), not a receive block hash.
- `HTTP 403 from Nano RPC` — retry shortly; the public `rpc.nano.to` node is
  rate-limited. Supply your own RPC via `NANO_RPC_URL` if you run at scale.

## License

Apache 2.0 (same as the repository).

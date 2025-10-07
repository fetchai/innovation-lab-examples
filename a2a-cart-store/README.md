# A2A Cart Store (Skyfire-enabled) — Example using uagents-adapter

This example demonstrates a minimal “store” A2A agent that supports add/remove/cart/checkout and integrates with Skyfire payments via the uAgents Chat/Payment protocol bridge.

- A2A server exposes a JSON‑RPC endpoint and returns AP2 artifacts (CartMandate, PaymentMandate, PaymentSuccess/Failure)
- A uAgent (SingleA2AAdapter) bridges A2A <-> uAgents Chat/Payment Protocols
- On checkout, a CartMandate is converted to RequestPayment for the UI; after payment, CommitPayment is converted to AP2 PaymentMandate and processed

## Run

```bash
# (Recommended) create venv and install deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt -r requirements.txt

# Configure environment
cp .env.example .env
# edit .env to set Skyfire + ports

# Start
python3 av_adapter.py
```

Defaults:
- A2A server: http://localhost:${STORE_A2A_PORT:-10031}
- uAgent: http://localhost:${STORE_UAGENT_PORT:-8230}

## Chat commands
- `list` or `catalog`
- `add <sku> [qty] [<sku> [qty]] ...` (e.g., `add book 1 pen 2 watch 1`)
- `remove <sku>`
- `cart`
- `checkout` (emits AP2 CartMandate → bridged to RequestPayment)

## How the bridge works
The adapter implements bidirectional conversion between AP2 (A2A) and uAgents Payment Protocol:

- AP2 CartMandate → Fetch.ai RequestPayment
  - amount/currency from `cart.contents.payment_request.details.total`
  - deadline from `cart.contents.cart_expiry`
  - metadata carries `cart_hash` and any method data (e.g., `skyfire_service_id`)
- Fetch.ai CommitPayment → AP2 PaymentMandate (forwarded to the A2A agent)
  - token from `CommitPayment.transaction_id` → `PaymentResponse.details.transaction_token`
  - total from `funds`
- AP2 PaymentSuccess → Fetch.ai CompletePayment
- AP2 PaymentFailure → Fetch.ai CancelPayment
- Fetch.ai RejectPayment → AP2 DenyCartMandate (forwarded to the A2A agent)

Adapter priorities when parsing A2A responses:
1) `parts[0].data` (AP2 objects) → return typed models
2) `parts[0].text` → return text
3) artifacts text (fallback)

## Skyfire integration
This example sets `supported_methods="skyfire"` in the CartMandate’s `PaymentRequest.method_data`. When the user confirms a payment:

1) UI sends Fetch.ai `CommitPayment` with `transaction_id` (Skyfire token) and `payment_method="skyfire"`
2) Adapter converts to AP2 `PaymentMandate` and forwards to the A2A store executor
3) Store executor verifies and charges the token:
   - Verify JWT against `JWKS_URL`, `JWT_ISSUER`, `SELLER_ACCOUNT_ID`; also checks `SELLER_SERVICE_ID` (ssi)
   - Charge via `SKYFIRE_TOKENS_CHARGE_API_URL` (or `SKYFIRE_TOKENS_API_URL`) using `SELLER_SKYFIRE_API_KEY`
4) On success, returns AP2 `PaymentSuccess` → bridged to Fetch.ai `CompletePayment`

Note: If any Skyfire env var is missing/invalid, you may see plain‑text errors (now forwarded by the adapter) or a CancelPayment.

## A2A JSON‑RPC shape (request)
```json
{
  "id": "<request_id>",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [ { "type": "text", "text": "checkout" } ],
      "messageId": "<message_id>"
    }
  }
}
```

## Troubleshooting
- “Unsupported response type” on payment: fixed; adapter now forwards text responses from A2A on CommitPayment
- “list index out of range”: ensure `PaymentRequest.method_data` is non‑empty (this example sets `skyfire`)
- Skyfire errors: check `.env` values and network path to JWKS/charge endpoints

## License
Apache 2.0

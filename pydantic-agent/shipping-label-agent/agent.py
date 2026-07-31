from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from uagents import Agent, Context

import payment
from chat_proto import chat_proto
from payment import payment_proto
from shipping import SHIPPO_TEST_PREFIX


def assert_test_keys() -> None:
    """Fail loudly unless Stripe and Shippo keys are test keys.

    This is the hard guarantee that no environment/config/fallback can select a
    live key: the process will not start otherwise.
    """
    payment.assert_stripe_test_keys()

    shippo_token = (os.getenv("SHIPPO_TOKEN") or "").strip()
    if not shippo_token.startswith(SHIPPO_TEST_PREFIX):
        raise RuntimeError(
            f"SHIPPO_TOKEN must be a test token starting with '{SHIPPO_TEST_PREFIX}'. "
            "This example is test-mode-only and will not run with a live token."
        )


agent = Agent(
    name=os.getenv("AGENT_NAME", "shipping-label-agent"),
    seed=os.environ.get("AGENT_SEED", "shipping-label-agent-dev-seed"),
    port=int(os.getenv("AGENT_PORT", "8090")),
    mailbox=True,
    publish_agent_details=True,
)

# ``ctx.storage`` persists to a JSON file on disk (``<name>_data.json``) and
# survives process restarts by design - that's what lets a genuinely long-lived
# conversation resume after a redeploy. But for this example, every fresh
# ``python agent.py`` run during development/review should behave like a brand
# new demo instance: pay again, no leftover state from a previous test run.
# Default true (an example agent, never a durable service); set to "false" to
# keep state across restarts if you want to test that persistence deliberately.
_RESET_STORAGE_ON_START = (os.getenv("RESET_STORAGE_ON_START", "true").strip().lower()) not in {
    "0",
    "false",
    "no",
}


@agent.on_event("startup")
async def startup(ctx: Context) -> None:
    assert_test_keys()
    if _RESET_STORAGE_ON_START:
        ctx.storage.clear()
        ctx.logger.info(
            "[agent] RESET_STORAGE_ON_START=true - wiped all session state; "
            "this run starts as a brand-new demo (pay again from message one)."
        )
    ctx.logger.info(f"[agent] {agent.name} | {agent.address}")
    ctx.logger.info(
        "[agent] TEST MODE only - Stripe test keys + Shippo test token. No real money moves."
    )
    port = os.getenv("AGENT_PORT", "8090")
    ctx.logger.info(
        f"[agent] Inspector: https://agentverse.ai/inspect/"
        f"?uri=http://127.0.0.1:{port}&address={agent.address}"
    )


agent.include(chat_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)


if __name__ == "__main__":
    # Fail fast before the server starts if keys aren't test keys.
    assert_test_keys()
    agent.run()

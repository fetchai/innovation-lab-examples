# nano-xno-payment-agent — seller example with a Nano (XNO) settlement rail.

import os

from dotenv import load_dotenv

load_dotenv()

from uagents import Agent, Context  # noqa: E402

from chat_proto import chat_proto  # noqa: E402
from payment import payment_proto  # noqa: E402

agent = Agent(
    name=os.getenv("AGENT_NAME", "Nano XNO Payment Agent"),
    seed=os.getenv("AGENT_SEED_PHRASE", "nano-xno-payment-agent-seed"),
    port=int(os.getenv("AGENT_PORT", "8000")),
    mailbox=True,
)

agent.include(chat_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("=== Nano XNO Payment Agent ===")
    ctx.logger.info("Collection rail: Nano (XNO) — feeless, single-block final")
    ctx.logger.info('payment_method="nano_xno", currency="XNO"')
    ctx.logger.info(f"NANO_ACCOUNT: {os.getenv('NANO_ACCOUNT', '(unset)')}")


if __name__ == "__main__":
    agent.run()

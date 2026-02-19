import os

import dotenv
from uagents import Agent

from chat_proto import build_chat_proto
from payment_proto import build_payment_proto

dotenv.load_dotenv()

# Load dotenv before importing modules that read env vars.
from handlers import on_chat, on_commit, on_reject  # noqa: E402


agent = Agent(
    name="stripe-horoscope-agent",
    seed=os.getenv("AGENT_SEED", "stripe-horoscope-agent-test"),
    port=int(os.getenv("AGENT_PORT", "8012")),
    mailbox=True,
    publish_agent_details=True,
)

agent.include(build_chat_proto(on_chat), publish_manifest=True)
agent.include(build_payment_proto(on_commit, on_reject), publish_manifest=True)

if __name__ == "__main__":
    agent.run()


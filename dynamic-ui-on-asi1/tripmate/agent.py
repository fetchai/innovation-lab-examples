"""TripMate uAgent entry point."""

import asyncio

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    chat_protocol_spec,
)

from tripmate.config import AGENT_NAME, AGENT_PORT, AGENT_SEED
from tripmate.handler import on_chat_message

# Python 3.12+ removed implicit event loop creation in the main thread.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
    publish_agent_details=True,
)

chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def on_message(ctx: Context, sender: str, msg: ChatMessage):
    await on_chat_message(ctx, sender, msg)


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"ACK from {sender[:16]}...")


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()

from __future__ import annotations

import os
import importlib.util
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    chat_protocol_spec,
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    MetadataContent,
    StartSessionContent,
    EndSessionContent,
)


def _load_workflow_module():
    here = os.path.dirname(__file__)
    workflow_path = os.path.join(here, "workflow.py")
    spec = importlib.util.spec_from_file_location("flight_tracker_workflow", workflow_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load workflow module spec")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


workflow_mod = _load_workflow_module()
run_workflow = getattr(workflow_mod, "run_workflow")
WorkflowInput = getattr(workflow_mod, "WorkflowInput")


agent = Agent(name="FlightTracker", seed="flight-tracker", mailbox=True, port=8000)
chat_proto = Protocol(spec=chat_protocol_spec)


def text_msg(text: str, *, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content)


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    # ACK immediately per protocol
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id
        ),
    )

    for item in msg.content:
        if isinstance(item, StartSessionContent):
            # Advertise capabilities (no attachments for this bridge)
            await ctx.send(
                sender,
                ChatMessage(
                    timestamp=datetime.now(timezone.utc),
                    msg_id=uuid4(),
                    content=[MetadataContent(type="metadata", metadata={"attachments": "false"})],
                ),
            )
            await ctx.send(sender, text_msg("Hi! Send a flight number like 'AI102 today'."))
            return

        if isinstance(item, TextContent):
            user_text = item.text.strip()
            if not user_text:
                await ctx.send(sender, text_msg("Please enter a flight query."))
                return
            try:
                result = await run_workflow(WorkflowInput(input_as_text=user_text))
                answer = (result or {}).get("output_text", "")
                await ctx.send(sender, text_msg(answer or "No answer returned."))
            except Exception as e:
                ctx.logger.exception("Workflow error")
                await ctx.send(sender, text_msg(f"Error: {e}"))
            return

    # If no supported content found
    await ctx.send(sender, text_msg("Unsupported message content."))


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"ACK from {sender} for {msg.acknowledged_msg_id}")


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()



"""
Gemini Task Manager Agent

A Fetch.ai uAgent that takes a user's goal or task and uses Google Gemini
to break it down into a clear, actionable step-by-step plan.
Supports the Chat Protocol so it can be used directly from ASI:One
or any other Agentverse-connected agent.
"""

import os
from datetime import datetime, timezone
from uuid import uuid4

from google import genai
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)


def generate_task_plan(goal: str) -> str:
    """Use Gemini to break a goal into a clear, actionable step-by-step plan."""
    goal = goal.strip()
    if not goal:
        return "Please send me a goal or task, e.g. 'Learn Python in 30 days' or 'Build a portfolio website'."

    if not GEMINI_API_KEY:
        return "This agent is missing a GEMINI_API_KEY — ask the operator to configure it."

    prompt = (
        f"You are a productivity expert. The user wants to achieve the following goal:\n\n"
        f"'{goal}'\n\n"
        f"Break this down into a clear, numbered, step-by-step action plan. "
        f"Keep each step concise and actionable. Maximum 7 steps. "
        f"End with one motivational sentence."
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    return response.text


def build_task_response(goal: str) -> str:
    """Build the full response string for a given goal."""
    plan = generate_task_plan(goal)
    return f"🎯 Task Plan for: '{goal}'\n\n{plan}"


chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    goal = "\n".join(
        item.text for item in msg.content if isinstance(item, TextContent) and item.text
    ).strip()

    if not goal:
        reply = (
            "Hi! Send me a goal or task and I'll break it down into "
            "a clear step-by-step action plan for you. "
            "Example: 'Learn machine learning in 60 days'"
        )
    else:
        try:
            reply = build_task_response(goal)
        except Exception as exc:
            ctx.logger.exception("Gemini API request failed")
            reply = f"Sorry, I couldn't generate a plan for '{goal}' right now ({exc})."

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=reply)],
        ),
    )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info(
        f"Received acknowledgement from {sender} for message {msg.acknowledged_msg_id}"
    )


agent = Agent()
agent.include(chat_proto, publish_manifest=True)


@agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info(f"Gemini Task Manager Agent started at address {agent.address}")
    ctx.logger.info(f"GEMINI_API_KEY configured: {bool(GEMINI_API_KEY)}")


if __name__ == "__main__":
    agent.run()

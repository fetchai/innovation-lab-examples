"""
Pharmacy Locator Agent

A uAgent that helps users find nearby pharmacies using the ASI:One LLM
to parse location queries and the free OpenStreetMap Overpass API to fetch data.
"""

from __future__ import annotations

import os
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

# Python 3.13 compatibility: Create an event loop if one doesn't exist
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import httpx
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol


load_dotenv()

from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

ASI_ONE_API_KEY = (os.getenv("ASI_ONE_API_KEY") or "").strip()


def _call_asi1_extract_location(user_text: str) -> str:
    """Use ASI:One to extract just the city/neighborhood name from the user query."""
    if not ASI_ONE_API_KEY:
        raise RuntimeError(
            "ASI_ONE_API_KEY is not set. Please add it to your .env file."
        )

    system_prompt = (
        "You are a helpful geographic assistant. "
        "Extract ONLY the city or neighborhood name from the user's request. "
        "Do not include any extra words, punctuation, or explanations. "
        "If no location is found, output exactly: UNKNOWN"
    )

    payload = {
        "model": "asi1",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.1,
        "max_tokens": 50,
    }

    headers = {
        "Authorization": f"Bearer {ASI_ONE_API_KEY}",
        "Content-Type": "application/json",
    }

    resp = httpx.post(
        "https://api.asi1.ai/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=30.0,
    )
    resp.raise_for_status()

    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("No response from ASI:One")

    location = choices[0]["message"]["content"].strip()
    return location


def _fetch_pharmacies_from_overpass(location: str) -> list[dict]:
    """Fetch pharmacies using the OpenStreetMap Overpass API."""
    overpass_url = "http://overpass-api.de/api/interpreter"

    # Overpass QL to find pharmacies in a specific named area
    query = f"""
    [out:json];
    area[name="{location}"]->.searchArea;
    node["amenity"="pharmacy"](area.searchArea);
    out 5;
    """

    headers = {"User-Agent": "PharmacyLocatorAgent/1.0 (Fetch.ai)", "Accept": "*/*"}
    resp = httpx.post(overpass_url, data={"data": query}, headers=headers, timeout=30.0)
    resp.raise_for_status()

    data = resp.json()
    elements = data.get("elements", [])

    results = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "Unnamed Pharmacy")
        address = tags.get("addr:street", "") + " " + tags.get("addr:city", "")
        phone = tags.get("phone", "No phone listed")
        opening_hours = tags.get("opening_hours", "Hours not specified")

        results.append(
            {
                "name": name,
                "address": address.strip() or "Address not specified",
                "phone": phone,
                "opening_hours": opening_hours,
            }
        )

    return results


chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    # Acknowledge the message immediately
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    # Extract user text
    parts = [
        item.text for item in msg.content if isinstance(item, TextContent) and item.text
    ]
    user_text = "\n".join(parts).strip()

    if not user_text:
        welcome = (
            "Hi! I'm the Pharmacy Locator Agent 🏥\n\n"
            "Tell me where you are, and I'll find nearby pharmacies for you.\n"
            "Example: 'Find a pharmacy in London' or 'Need meds near Brooklyn'"
        )
        await _send_reply(ctx, sender, welcome)
        return

    try:
        # Step 1: Use LLM to extract the location from natural language
        location = _call_asi1_extract_location(user_text)
        ctx.logger.info(f"Extracted location: {location}")

        if location == "UNKNOWN":
            await _send_reply(
                ctx,
                sender,
                "I couldn't figure out the location from your message. Please specify a city or neighborhood!",
            )
            return

        await _send_reply(
            ctx, sender, f"Searching for pharmacies in **{location}**... 🔍"
        )

        # Step 2: Query the Overpass API
        pharmacies = _fetch_pharmacies_from_overpass(location)

        if not pharmacies:
            await _send_reply(
                ctx,
                sender,
                f"Sorry, I couldn't find any pharmacies listed in OpenStreetMap for {location}.",
            )
            return

        # Step 3: Format the response
        response_text = (
            f"Here are {len(pharmacies)} pharmacies I found in {location}:\n\n"
        )
        for i, p in enumerate(pharmacies, 1):
            response_text += f"{i}. **{p['name']}**\n"
            response_text += f"   📍 Address: {p['address']}\n"
            response_text += f"   📞 Phone: {p['phone']}\n"
            response_text += f"   🕒 Hours: {p['opening_hours']}\n\n"

        response_text += "\n*Data provided by OpenStreetMap (Overpass API)*"

        await _send_reply(ctx, sender, response_text.strip())

    except Exception as e:
        ctx.logger.exception("Agent encountered an error")
        await _send_reply(ctx, sender, f"Sorry, I encountered an error: {str(e)[:200]}")


async def _send_reply(ctx: Context, sender: str, text: str):
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=text)],
        ),
    )


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"ACK received from {sender}")


agent = Agent(
    name="pharmacy-locator-agent", seed="random_seed_for_pharmacy_locator_agent_123"
)
agent.include(chat_proto, publish_manifest=True)


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"Pharmacy Locator Agent started -> {agent.address}")
    ctx.logger.info(f"ASI:One API key present: {bool(ASI_ONE_API_KEY)}")


if __name__ == "__main__":
    agent.run()

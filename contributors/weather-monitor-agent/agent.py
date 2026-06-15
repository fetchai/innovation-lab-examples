"""
Real-time Weather Monitoring Agent
===================================
Accepts a city name via the uAgents chat protocol,
fetches live data from OpenWeatherMap (free tier),
and returns temperature, humidity, wind speed, and
weather condition. Alerts the user if temperature
crosses a configurable threshold.

Usage:
    python agent.py
"""

import os
import re
from datetime import datetime
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────
OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
AGENTVERSE_API_KEY: str = os.getenv("AGENTVERSE_API_KEY", "")
AGENT_SEED:         str = os.getenv("AGENT_SEED", "weather-monitor-agent-seed-phrase")
AGENT_PORT:         int = int(os.getenv("AGENT_PORT", "8010"))

# Alert when temperature exceeds this value (°C).  Override via .env.
TEMP_ALERT_THRESHOLD: float = float(os.getenv("TEMP_ALERT_THRESHOLD", "35.0"))

OWM_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# ── Agent initialisation ────────────────────────────────────────────────────────
agent = Agent(
    name="WeatherMonitorAgent",
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=f"{AGENTVERSE_API_KEY}@https://agentverse.ai" if AGENTVERSE_API_KEY else None,
)

chat_proto = Protocol(spec=chat_protocol_spec)


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _make_chat(text: str, end_session: bool = False) -> ChatMessage:
    """Wrap plain text into a ChatMessage envelope."""
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )


def _extract_city(raw: str) -> str:
    """
    Pull a city name out of free-form user text.
    Examples handled:
        "weather in Mumbai"
        "What's the weather in New Delhi?"
        "London"
        "temperature of Paris"
    """
    raw = raw.strip()
    patterns = [
        r"(?:weather|temperature|temp|forecast)\s+(?:in|for|of)\s+(.+)",
        r"(?:in|for|of)\s+(.+?)(?:\s*\?)?$",
    ]
    for pat in patterns:
        m = re.search(pat, raw, re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip("?")
    # Fall back: use the whole message as the city name (handles bare "Mumbai")
    return raw.rstrip("?").strip()


async def _fetch_weather(city: str) -> dict | None:
    """
    Call OpenWeatherMap and return a parsed dict, or None on failure.
    Returned keys: city, country, condition, temp_c, feels_like_c,
                   humidity_pct, wind_kph, alert
    """
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(OWM_BASE_URL, params=params)
            if resp.status_code == 401:
                return {"error": "invalid_api_key"}
            if resp.status_code == 404:
                return {"error": "city_not_found"}
            resp.raise_for_status()
            data = resp.json()
    except httpx.RequestError as exc:
        return {"error": f"network_error: {exc}"}

    temp_c      = data["main"]["temp"]
    feels_like  = data["main"]["feels_like"]
    humidity    = data["main"]["humidity"]
    wind_kph    = round(data["wind"]["speed"] * 3.6, 1)   # m/s → km/h
    condition   = data["weather"][0]["description"].capitalize()
    city_name   = data["name"]
    country     = data["sys"]["country"]

    return {
        "city":         city_name,
        "country":      country,
        "condition":    condition,
        "temp_c":       temp_c,
        "feels_like_c": feels_like,
        "humidity_pct": humidity,
        "wind_kph":     wind_kph,
        "alert":        temp_c > TEMP_ALERT_THRESHOLD,
    }


def _format_response(w: dict) -> str:
    """Turn the weather dict into a human-readable reply."""
    alert_line = (
        f"\n🚨 *Heat Alert!* Temperature is above {TEMP_ALERT_THRESHOLD}°C — "
        "stay hydrated and avoid direct sunlight."
        if w["alert"]
        else ""
    )
    return (
        f"🌤️  *Weather in {w['city']}, {w['country']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌡️  Temperature : {w['temp_c']:.1f}°C  (feels like {w['feels_like_c']:.1f}°C)\n"
        f"💧  Humidity    : {w['humidity_pct']}%\n"
        f"💨  Wind speed  : {w['wind_kph']} km/h\n"
        f"☁️  Condition   : {w['condition']}"
        f"{alert_line}"
    )


# ── Chat protocol handlers ──────────────────────────────────────────────────────

@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Message from {sender}")

    # 1. Acknowledge immediately (protocol requirement)
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.utcnow(),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    # 2. Extract user text
    user_text = ""
    for block in msg.content:
        if isinstance(block, StartSessionContent):
            # Session just opened – send a greeting and wait
            await ctx.send(
                sender,
                _make_chat(
                    "👋 Hello! I'm the **Weather Monitor Agent**.\n\n"
                    "Send me a city name and I'll fetch live weather data for you.\n"
                    "Example: `weather in Mumbai`  or just  `Tokyo`"
                ),
            )
            return
        if isinstance(block, TextContent):
            user_text += block.text + " "

    user_text = user_text.strip()
    if not user_text:
        return

    # 3. Guard: API key must be set
    if not OPENWEATHER_API_KEY:
        await ctx.send(
            sender,
            _make_chat(
                "⚠️ OPENWEATHER_API_KEY is not set in the environment.\n"
                "Please add it to your `.env` file and restart the agent.\n"
                "Get a free key at https://openweathermap.org/api"
            ),
        )
        return

    # 4. Identify city and call the API
    city = _extract_city(user_text)
    ctx.logger.info(f"Fetching weather for: {city!r}")

    result = await _fetch_weather(city)

    # 5. Build reply
    if result is None or "error" in result:
        err = (result or {}).get("error", "unknown")
        if err == "invalid_api_key":
            reply = (
                "❌ Your OpenWeatherMap API key appears to be invalid.\n"
                "Check the value of OPENWEATHER_API_KEY in your `.env` file."
            )
        elif err == "city_not_found":
            reply = (
                f"❌ I couldn't find a city called **{city}**.\n"
                "Try a different spelling or include the country code, e.g. `Paris,FR`."
            )
        else:
            reply = f"❌ Something went wrong while fetching weather data: `{err}`"
    else:
        reply = _format_response(result)

    await ctx.send(sender, _make_chat(reply, end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Acknowledgement received from {sender}")


# ── Startup ─────────────────────────────────────────────────────────────────────

@agent.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info(f"Weather Monitor Agent started  |  address: {ctx.agent.address}")
    ctx.logger.info(f"Temperature alert threshold    : {TEMP_ALERT_THRESHOLD}°C")
    if not OPENWEATHER_API_KEY:
        ctx.logger.warning(
            "OPENWEATHER_API_KEY is not set – weather queries will fail until it is added."
        )
    if not AGENTVERSE_API_KEY:
        ctx.logger.info(
            "AGENTVERSE_API_KEY not set – running in local-only mode (no Agentverse registration)."
        )


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
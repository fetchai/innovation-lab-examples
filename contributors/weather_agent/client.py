"""
weather-agent/client.py
------------------------
A uAgents client that sends a WeatherRequest to the weather agent
and pretty-prints the WeatherResponse it receives back.

Usage:
    python client.py              # defaults to London
    python client.py "Tokyo"
    python client.py "Chennai"
"""

import sys
from uagents import Agent, Context

from models import WeatherRequest, WeatherResponse  # ← shared schemas

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Copy the address printed by agent.py on startup and paste it here.
WEATHER_AGENT_ADDRESS = (
    "agent1q200mh5dht5rpnz3yk0zu8fjndd2m9pdyup7e9rprnjvnxusaqjzg79ttmd"
)

CITY = sys.argv[1] if len(sys.argv) > 1 else "London"

# ---------------------------------------------------------------------------
# Client agent
# ---------------------------------------------------------------------------

client = Agent(
    name="weather_client",
    seed="weather-client-seed-v1",
    port=8001,
    endpoint=["http://localhost:8001/submit"],
)


def _banner(title: str) -> str:
    return f"\n{'─' * 50}\n  {title}\n{'─' * 50}"


@client.on_event("startup")
async def send_request(ctx: Context):
    ctx.logger.info(f"Client started  |  address: {ctx.agent.address}")
    ctx.logger.info(f"Querying weather for '{CITY}' …")
    await ctx.send(WEATHER_AGENT_ADDRESS, WeatherRequest(city=CITY))


@client.on_message(model=WeatherResponse)
async def handle_response(ctx: Context, sender: str, msg: WeatherResponse):
    if msg.error:
        print(_banner("⚠  Weather Agent Error"))
        print(f"  {msg.error}")
    else:
        print(_banner(f"🌤  Weather Report — {msg.city}"))
        print(f"  Condition    : {msg.description}")
        print(f"  Temperature  : {msg.temperature_c} °C")
        print(f"  Feels like   : {msg.feels_like_c} °C")
        print(f"  Humidity     : {msg.humidity_percent} %")
        print(f"  Wind speed   : {msg.wind_speed_kmh} km/h")
    print()


if __name__ == "__main__":
    client.run()

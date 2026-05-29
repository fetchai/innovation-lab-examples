"""
weather-agent/agent.py
-----------------------
A Fetch.ai uAgent that accepts a city name and returns current weather
data from the free Open-Meteo API (no API key required).

Run:
    python agent.py
"""

import requests
from uagents import Agent, Context

from models import WeatherRequest, WeatherResponse  # ← shared schemas

# ---------------------------------------------------------------------------
# Geocoding + weather helpers
# ---------------------------------------------------------------------------

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Icy fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight showers",
    81: "Moderate showers",
    82: "Violent showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm w/ slight hail",
    99: "Thunderstorm w/ heavy hail",
}


def geocode_city(city: str) -> tuple[float, float, str] | None:
    try:
        resp = requests.get(
            GEOCODING_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results")
        if not results:
            return None
        r = results[0]
        parts = [r.get("name", city)]
        if r.get("country"):
            parts.append(r["country"])
        return r["latitude"], r["longitude"], ", ".join(parts)
    except requests.RequestException:
        return None


def fetch_weather(lat: float, lon: float) -> dict | None:
    try:
        resp = requests.get(
            WEATHER_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": [
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "wind_speed_10m",
                    "weathercode",
                ],
                "timezone": "auto",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("current", {})
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

AGENT_SEED = "weather-agent-open-meteo-seed-v1"

weather_agent = Agent(
    name="weather_agent",
    seed=AGENT_SEED,
    port=8000,
    endpoint=["http://localhost:8000/submit"],
)


@weather_agent.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info(f"Weather Agent started  |  address: {ctx.agent.address}")
    ctx.logger.info("Waiting for WeatherRequest messages …")


@weather_agent.on_message(model=WeatherRequest, replies={WeatherResponse})
async def handle_weather_request(ctx: Context, sender: str, msg: WeatherRequest):
    city = msg.city.strip()
    ctx.logger.info(f"Request for '{city}' from {sender}")

    geo = geocode_city(city)
    if geo is None:
        await ctx.send(
            sender,
            WeatherResponse(
                city=city,
                temperature_c=0,
                feels_like_c=0,
                wind_speed_kmh=0,
                humidity_percent=0,
                description="",
                error=f"City '{city}' not found. Please check the spelling.",
            ),
        )
        return

    lat, lon, display_name = geo
    current = fetch_weather(lat, lon)
    if current is None:
        await ctx.send(
            sender,
            WeatherResponse(
                city=display_name,
                temperature_c=0,
                feels_like_c=0,
                wind_speed_kmh=0,
                humidity_percent=0,
                description="",
                error="Failed to retrieve weather data. Please try again.",
            ),
        )
        return

    wmo_code = int(current.get("weathercode", 0))
    response = WeatherResponse(
        city=display_name,
        temperature_c=round(current.get("temperature_2m", 0), 1),
        feels_like_c=round(current.get("apparent_temperature", 0), 1),
        wind_speed_kmh=round(current.get("wind_speed_10m", 0), 1),
        humidity_percent=int(current.get("relative_humidity_2m", 0)),
        description=WMO_CODES.get(wmo_code, f"WMO code {wmo_code}"),
    )
    ctx.logger.info(
        f"Replying: {display_name} | {response.temperature_c}°C | {response.description}"
    )
    await ctx.send(sender, response)


if __name__ == "__main__":
    weather_agent.run()

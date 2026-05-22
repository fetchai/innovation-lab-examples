"""
weather-agent/models.py
------------------------
Single source of truth for all message schemas shared between
agent.py and client.py.

uAgents derives a schema digest from the class definition — both
sides MUST import from the same module to get identical digests.
"""

from uagents import Model


class WeatherRequest(Model):
    """Sent by the client: the city name to look up."""
    city: str


class WeatherResponse(Model):
    """Returned by the agent: current weather conditions."""
    city: str
    temperature_c: float
    feels_like_c: float
    wind_speed_kmh: float
    humidity_percent: int
    description: str
    error: str = ""
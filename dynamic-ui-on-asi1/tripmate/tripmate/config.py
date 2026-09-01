"""TripMate configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY", "")
ASI_ONE_BASE_URL = "https://api.asi1.ai/v1"
ASI_ONE_MODEL = "asi1"

AGENT_NAME = "TripMate"
AGENT_SEED = "TripMate"
AGENT_PORT = int(os.getenv("PORT", "8000"))

MCP_COMMAND = "npx"
MCP_ARGS = ["mcp-remote", "https://mcp.lastminute.com/mcp"]
MCP_STARTUP_TIMEOUT = 20
MCP_RPC_TIMEOUT = 90

CITY_IATA = {
    "ROME": "FCO",
    "ROMA": "FCO",
    "MILAN": "MXP",
    "MILANO": "MXP",
    "MADRID": "MAD",
    "LONDON": "LHR",
    "PARIS": "CDG",
    "BARCELONA": "BCN",
    "BERLIN": "BER",
    "AMSTERDAM": "AMS",
    "DUBAI": "DXB",
    "TOKYO": "NRT",
    "NEW YORK": "JFK",
    "LOS ANGELES": "LAX",
    "SINGAPORE": "SIN",
}

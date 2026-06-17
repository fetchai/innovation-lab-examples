import os
from pathlib import Path
from dotenv import load_dotenv

# Load from .llm.env in the project root (one level up from scripts/)
_env_path = Path(__file__).parent.parent / ".llm.env"
load_dotenv(_env_path)

ASI_ONE_API_KEY = os.environ["ASI_ONE_API_KEY"]
ASI_ONE_BASE_URL = "https://api.asi1.ai/v1"
ASI_ONE_MODEL = "asi1-mini"

CRAWL4AI_BASE = "http://localhost:11235"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Sources to crawl: name → listing URL
SOURCES = {
    "cerebralvalley": "https://cerebralvalley.ai/events?locations=ALL",
}

BASE_URLS = {
    "cerebralvalley": "https://cerebralvalley.ai",
}

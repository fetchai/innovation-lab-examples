"""
Configuration: API keys, model names, constants.
All tunables in one place.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Scene / timing ──────────────────────────────────────────────
SCENE_COUNT = 8
SCENE_DURATION_SECONDS = 8
MAX_RETRIES = 2

# ── Model names ─────────────────────────────────────────────────
VEO_MODEL = "veo-3.1-generate-preview"
VEO_RESOLUTION = "720p"
VEO_ASPECT_RATIO = "16:9"

TTS_MODEL = "gemini-2.5-flash-preview-tts"
TTS_DEFAULT_VOICE = "Puck"

LYRIA_MODEL = "models/lyria-realtime-exp"
LYRIA_SAMPLE_RATE = 48000
LYRIA_CHANNELS = 2

CREATIVE_MODEL = "gemini-2.5-flash"
SAFETY_MODEL = "gemini-2.5-flash"
IMAGE_GEN_MODEL = "gemini-2.5-flash-image"

# ── API key pool ────────────────────────────────────────────────
# 5 keys — max 2 concurrent Veo calls per key.
# Mapping:  key 0 → scenes 0,1 + safety/creative
#           key 1 → scenes 2,3
#           key 2 → scenes 4,5
#           key 3 → scenes 6,7
#           key 4 → opening + closing videos

API_KEYS = [
    os.getenv("7GEMINI_API_KEY"),  # key 0 → scenes 0,1 + safety + creative
    os.getenv("9GEMINI_API_KEY"),  # key 1 → scenes 2,3
    os.getenv("10GEMINI_API_KEY"),  # key 2 → scenes 4,5
    os.getenv("11GEMINI_API_KEY"),  # key 3 → scenes 6,7
    os.getenv("12GEMINI_API_KEY"),  # key 4 → opening + closing
]

# Validate at import time
for i, k in enumerate(API_KEYS):
    if not k:
        raise ValueError(f"API_KEYS[{i}] is not set. Check your .env file.")


def key_for_scene(scene_index: int) -> str:
    """Return the API key assigned to a given scene index (0-7)."""
    return API_KEYS[scene_index // 2]


def key_index_for_scene(scene_index: int) -> int:
    """Return the key pool index (0-3) for a given scene index."""
    return scene_index // 2


# Convenience aliases
SAFETY_KEY = API_KEYS[0]
CREATIVE_KEY = API_KEYS[0]
OPENING_KEY = API_KEYS[4]  # dedicated key for opening
CLOSING_KEY = API_KEYS[4]  # dedicated key for closing

# ── GCS ─────────────────────────────────────────────────────────
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GCS_CREDENTIALS_BASE64 = os.getenv("GCS_CREDENTIALS_BASE64")

# ── Agent identity ──────────────────────────────────────────────
AGENT_NAME = "unified_movie_agent"
AGENT_SEED = "unified-movie-agent-seed-2025"
AGENT_PORT = 8001

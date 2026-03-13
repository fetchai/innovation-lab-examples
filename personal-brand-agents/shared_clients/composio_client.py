import os
from composio import Composio
from dotenv import load_dotenv

load_dotenv()

COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")

if COMPOSIO_API_KEY is None:
    raise ValueError("Missing required environment variable: COMPOSIO_API_KEY")


LINKEDIN_AUTH_CONFIG_ID = "ac_S29IN2PEi_IR"
composio = Composio(api_key=COMPOSIO_API_KEY)
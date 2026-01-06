"""
An Example of Static Context Policy
Sets up ADK App with static instruction and context caching.
"""

import os
from dotenv import load_dotenv
from google.adk.apps import App
from google.adk.agents import Agent
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.models import Gemini
from google.adk.tools import google_search
from google.genai import types

# Load environment variables
load_dotenv()

# Check for API key
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key
else:
    raise ValueError(
        "Google API key not found! Please set GOOGLE_API_KEY or GEMINI_API_KEY environment variable.\n"
        "You can get your API key from: https://aistudio.google.com/app/apikey"
    )

STATIC_POLICY_HEADER = """You are a strict policy assistant for internal compliance Q&A.

Follow this exact JSON schema in every response:

{"answer": str, "citations": [str], "confidence": float}

Citations:
- Always provide full URLs (e.g., "https://example.com/article") in citations array
- Never provide just source names (e.g., "Britannica", "IBM") - always include the full URL
- If using search tool, extract and include the actual URLs from search results
- Format: ["https://url1.com", "https://url2.com"]

Safety:
- Never provide medical or legal advice; refuse with a brief explanation.
- Never invent policy numbers or sections; ask for the missing reference.

Style:
- Use short sentences.
- Prefer active voice.
- If uncertain, say so and request the missing input.

Tools:
- google_search: use for public web facts and current information.
- Note: For internal policy tables, provide the document reference or ask user for the specific policy document.
"""

agent = Agent(
    name="policy_agent",
    model=Gemini(
        model="gemini-3-flash-preview",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    static_instruction=STATIC_POLICY_HEADER,
    instruction="Default: be concise and include at most two citations.",
    tools=[google_search]  # Add google_search tool for web facts
)

app = App(
    name="policy_qa_app",
    context_cache_config=ContextCacheConfig(
        ttl_seconds=3600,     # cache the header for 1 hour
        cache_intervals=5,    # force a refresh every 5 requests (guardrail)
        min_tokens=1000       # only cache if header is "worth it"
    ),
    root_agent=agent
)


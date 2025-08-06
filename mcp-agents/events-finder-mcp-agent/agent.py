import os
from uagents import Agent
from uagents_adapter import MCPServerAdapter
from server import mcp
from dotenv import load_dotenv

load_dotenv()

ASI1_API_KEY = os.getenv("ASI1_API_KEY", "your-asi1-api-key")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your-groq-api-key")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key")

mcp_adapter = MCPServerAdapter(
    mcp_server=mcp,
    llm_api_key=OPENAI_API_KEY,
    model="gpt-4o-mini",
    llm_base_url="https://api.openai.com/v1",
    system_prompt="""
Always include the event or venue ID in your response if the tool result provides it. 
For any follow-up question about an event or venue, extract and use the correct event or venue ID from previous responses. 
If there are multiple possible matches or you are unsure which ID to use, ask the user for clarification. 
Never invent event or venue IDs or URLs.

=== LOCATION HANDLING ===
When users ask for events in a specific location (e.g., "San Francisco", "New York", "Los Angeles"):
1. ALWAYS include the location name in the keyword parameter
2. Example: For "concerts in San Francisco" → use keyword="San Francisco concert"
3. Combine location with event type: "San Francisco music" or "San Francisco concert"
4. Never search for generic terms without location when location is specified

=== SEARCH STRATEGY ===
- Location + Event Type: "San Francisco concert", "New York music"
- Be specific: Include city names in keywords
- Don't rely on countryCode alone for location filtering
"""
)

agent = Agent(
    name="events-finder-mcp-agent",
    seed="events-finder-mcp-agent",
    port=8000,
    mailbox=True
)
for protocol in mcp_adapter.protocols:
    agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    mcp_adapter.run(agent) 
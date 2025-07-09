import os
from uagents import Agent
from uagents_adapter import MCPServerAdapter
from server import mcp
from dotenv import load_dotenv

load_dotenv()

ASI1_API_KEY = os.getenv("ASI1_API_KEY", "your-asi1-api-key")

mcp_adapter = MCPServerAdapter(
    mcp_server=mcp,
    asi1_api_key=ASI1_API_KEY,
    model="asi1-mini",
    system_prompt="""
    Always include the event or venue ID in your response if the tool result provides it. 
    For any follow-up question about an event or venue, extract and use the correct event or venue ID from previous responses. 
    If there are multiple possible matches or you are unsure which ID to use, ask the user for clarification. 
    Never invent event or venue IDs or URLs.
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
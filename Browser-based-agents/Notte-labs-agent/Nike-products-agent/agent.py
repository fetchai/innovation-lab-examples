"""
Nike Scraper Agent with ASI1 LLM compatibility.

This agent scrapes Nike products and categories and makes them available through
natural language queries via ASI1 LLM integration.
"""

import os
from enum import Enum
import asyncio

from uagents import Agent, Context, Model
from uagents.experimental.quota import QuotaProtocol, RateLimit
from uagents_core.models import ErrorMessage

from chat_proto import chat_proto, struct_output_client_proto
from nike_scraper import get_nike_info_enhanced, NikeScrapeRequest, NikeScrapeResponse

# Create the agent with mailbox=True for ASI1 discoverability
agent = Agent(
    name="nike_scraper",
    port=8000,
    mailbox=True        
)

# Print the agent's address for reference
print(f"Your Nike Scraper agent's address is: {agent.address}")

# Set up rate limiting protocol
proto = QuotaProtocol(
    storage_reference=agent.storage,
    name="Nike-Scraper-Protocol",
    version="0.1.0",
    default_rate_limit=RateLimit(window_size_minutes=60, max_requests=30),
)

# Handle direct Nike scraper requests (without natural language processing)
@proto.on_message(
    NikeScrapeRequest, replies={NikeScrapeResponse, ErrorMessage}
)
async def handle_request(ctx: Context, sender: str, msg: NikeScrapeRequest):
    """
    Handle direct structured requests for Nike product information.
    This allows other agents to communicate directly with this agent
    using the NikeScrapeRequest model.
    """
    ctx.logger.info(f"Received Nike scrape request: action={msg.action}, category={msg.category_name}")
    
    try:
        # Process the request using the nike_scraper module
        nike_response = await get_nike_info_enhanced(request=msg)
        
        ctx.logger.info(f"Successfully processed Nike request")
        await ctx.send(sender, NikeScrapeResponse(results=nike_response.results))
        
    except Exception as err:
        ctx.logger.error(f"Error in handle_request: {err}")
        await ctx.send(sender, ErrorMessage(error=str(err)))

# Health check functionality
def agent_is_healthy() -> bool:
    """
    Implement the actual health check logic here.
    For example, check if the agent can connect to the Nike website.
    """
    try:
        import requests
        response = requests.get("https://www.nike.com", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

class HealthCheck(Model):
    pass

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"

class AgentHealth(Model):
    agent_name: str
    status: HealthStatus

health_protocol = QuotaProtocol(
    storage_reference=agent.storage, name="HealthProtocol", version="0.1.0"
)

@health_protocol.on_message(HealthCheck, replies={AgentHealth})
async def handle_health_check(ctx: Context, sender: str, msg: HealthCheck):
    """Handle health check requests to monitor agent status."""
    status = HealthStatus.UNHEALTHY
    try:
        if agent_is_healthy():
            status = HealthStatus.HEALTHY
    except Exception as err:
        ctx.logger.error(f"Health check error: {err}")
    finally:
        await ctx.send(sender, AgentHealth(agent_name="nike_scraper", status=status))

# Register all protocols with the agent
agent.include(proto, publish_manifest=True)
agent.include(health_protocol, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)
agent.include(struct_output_client_proto, publish_manifest=True)

if __name__ == "__main__":
    # Check if NOTTE_API_KEY is set
    if not os.environ.get("NOTTE_API_KEY"):
        print("Warning: NOTTE_API_KEY environment variable is not set.")
        print("The agent will run but scraping functionality will be limited.")
    
    # Run the agent
    print("Starting Nike Scraper Agent...")
    print("This agent can respond to natural language queries about Nike products via ASI1 LLM.")
    print("Example queries:")
    print("- Show me Nike categories")
    print("- List Nike basketball shoes")
    print("- Get Nike running products")
    agent.run()

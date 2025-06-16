# agent.py
import os
from enum import Enum
import asyncio

from uagents import Agent, Context, Model
from uagents.experimental.quota import QuotaProtocol, RateLimit
from uagents_core.models import ErrorMessage

from chat_proto import chat_proto, AirbnbRequest, AirbnbResponse, struct_output_client_proto
from mcp_client import connect_to_airbnb_mcp, cleanup_mcp_connection, search_airbnb_listings

# Create the agent
agent = Agent(
    name="airbnb_assistant",
    port=8004,
    mailbox=True
)

# Print the agent's address for reference
print(f"Your agent's address is: {agent.address}")

# Set up rate limiting protocol
proto = QuotaProtocol(
    storage_reference=agent.storage,
    name="Airbnb-Protocol",
    version="0.1.0",
    default_rate_limit=RateLimit(window_size_minutes=60, max_requests=30),
)

# Health check implementation
def agent_is_healthy() -> bool:
    """Check if the agent's Airbnb capabilities are working"""
    try:
        from mcp_client import mcp_session
        return mcp_session is not None
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

class HealthCheck(Model):
    pass

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"

class AgentHealth(Model):
    agent_name: str
    status: HealthStatus

# Health monitoring protocol
health_protocol = QuotaProtocol(
    storage_reference=agent.storage, name="HealthProtocol", version="0.1.0"
)

@health_protocol.on_message(HealthCheck, replies={AgentHealth})
async def handle_health_check(ctx: Context, sender: str, msg: HealthCheck):
    status = HealthStatus.UNHEALTHY
    try:
        if agent_is_healthy():
            status = HealthStatus.HEALTHY
    except Exception as err:
        ctx.logger.error(f"Health check error: {err}")
    finally:
        await ctx.send(
            sender, 
            AgentHealth(agent_name="airbnb_assistant", status=status)
        )

# Handle direct Airbnb requests
@proto.on_message(
    AirbnbRequest, replies={AirbnbResponse, ErrorMessage}
)
async def handle_airbnb_request(ctx: Context, sender: str, msg: AirbnbRequest):
    ctx.logger.info(f"Received direct Airbnb request of type: {msg.request_type}")
    try:
        if msg.request_type == "search":
            location = msg.parameters.get("location")
            if not location:
                raise ValueError("Missing location parameter")
            
            limit = msg.parameters.get("limit", 2)
            
            # Search for listings
            search_result = await search_airbnb_listings(location, limit)
            
            # Format the results
            result = f"Here are {limit} Airbnb rentals in {location}:\n\n"
            
            listings = search_result.get("listings", [])
            for i, listing in enumerate(listings[:limit], 1):
                result += f"{i}. {listing.get('name', 'Unnamed Listing')}\n"
                result += f"   Price: {listing.get('price', 'Price not available')}\n"
                result += f"   Rating: {listing.get('rating', 'Not rated')}\n\n"
            
            # Send the response
            ctx.logger.info(f"Successfully processed Airbnb search request for {location}")
            await ctx.send(sender, AirbnbResponse(results=result))
            
        elif msg.request_type == "details":
            listing_id = msg.parameters.get("listing_id")
            if not listing_id:
                raise ValueError("Missing listing_id parameter")
            
            # This would call a function to get listing details
            # For now, just return a placeholder message
            result = f"Details for listing {listing_id} are not available yet."
            
            # Send the response
            ctx.logger.info(f"Processed listing details request for {listing_id}")
            await ctx.send(sender, AirbnbResponse(results=result))
            
        else:
            result = f"Unknown request type: {msg.request_type}"
            ctx.logger.error(result)
            await ctx.send(sender, ErrorMessage(error=result))
            
    except Exception as err:
        ctx.logger.error(f"Error in handle_airbnb_request: {err}")
        await ctx.send(sender, ErrorMessage(error=str(err)))

# Include all protocols
agent.include(health_protocol, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)
agent.include(struct_output_client_proto, publish_manifest=True)
agent.include(proto, publish_manifest=True)

# Initialize MCP connection on startup
@agent.on_event("startup")
async def on_startup(ctx: Context):
    """Connect to MCP server on startup"""
    ctx.logger.info("Connecting to Airbnb MCP server on startup")
    success = await connect_to_airbnb_mcp()
    if success:
        ctx.logger.info("Successfully connected to Airbnb MCP server")
    else:
        ctx.logger.error("Failed to connect to Airbnb MCP server")

if __name__ == "__main__":
    try:
        # Run the agent
        agent.run()
    except KeyboardInterrupt:
        print("Shutting down...")
        asyncio.run(cleanup_mcp_connection())
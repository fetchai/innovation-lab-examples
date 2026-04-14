import logging
from dotenv import load_dotenv
from uagents import Agent, Context
from mcp_client import fetch_mcp_tools, check_api_health
from chat_protocol import chat_proto

# Load environment configuration from .env file
load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Logging Configuration
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)-24s │ %(message)s",
    datefmt="%H:%M:%S",
)

# Our modules — full detail
logging.getLogger("mcp_client").setLevel(logging.DEBUG)
logging.getLogger("chat_protocol").setLevel(logging.DEBUG)

# HTTP traffic — INFO so we see request/response status lines
logging.getLogger("httpx").setLevel(logging.INFO)

# MCP internals — WARNING only (suppress session negotiation noise)
logging.getLogger("mcp").setLevel(logging.WARNING)

# Suppress the benign "Session termination failed: 500" from the
# TicketLens MCP server — known server-side cleanup issue, no impact.
logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)

# uagents registration noise — WARNING only
logging.getLogger("uagents").setLevel(logging.WARNING)

# Initialize uAgent with ASI1/Agentverse compatibility
agent = Agent(
    name="ticketlens_agent",
    port=8000,
    seed="ticketlens_agent_seed_phrase",
    mailbox=True,
    enable_agent_inspector=True,
)


@agent.on_event("startup")
async def startup(ctx: Context):
    """
    At startup, connect briefly to the remote MCP server to fetch and cache
    tool definitions. These are passed to the reasoning loop on each request.
    If the server is temporarily unavailable, the agent logs a warning and
    continues — the chat handler will attempt a lazy re-bootstrap on first use.
    """
    ctx.logger.info(
        "Bootstrapping: Fetching remote tool capabilities from TicketLens MCP..."
    )

    # Part 3: Storage Maintenance (Bulk Cleanup)
    try:
        import time

        count = 0
        # Access the internal dict of the KeyValueStore for pruning
        storage_dict = getattr(ctx.storage, "_data", {})
        for key in list(storage_dict.keys()):
            # 1. Prune Expired MCP Cache (Tours/POIs)
            if key.startswith("mcp_cache:"):
                val = storage_dict.get(key)
                if isinstance(val, dict) and time.time() > val.get("expiry", 0):
                    storage_dict.pop(key, None)
                    count += 1

            # 2. Prune Stale User Sessions (Inactive > 24 hours)
            elif key.startswith("history_"):
                val = storage_dict.get(key)
                if isinstance(val, dict):
                    last_active = val.get("last_active", 0)
                    # 24 hours = 86,400 seconds
                    if time.time() - last_active > 86400:
                        storage_dict.pop(key, None)
                        count += 1

        if count > 0:
            ctx.logger.info(
                f"[MCP] [CLEANUP] Pruned {count} stale cache/session entries from storage."
            )
    except Exception as e:
        ctx.logger.debug(f"Non-critical cleanup failure: {e}")

    try:
        # 5 retries, 3s base backoff (2s, 4s, 6s, 8s, 10s = up to ~30s total wait)
        tools_metadata = await fetch_mcp_tools(retries=5, backoff=2.0)
        ctx.storage.set("tools_metadata", tools_metadata)
        ctx.logger.info(f"Bootstrap complete. {len(tools_metadata)} tool(s) loaded.")
    except BaseException as e:
        health = await check_api_health()
        if health == "rate_limited":
            ctx.logger.warning(
                "Bootstrap failed: TicketLens API daily rate limit (100 req/day per IP) exceeded. "
                "Agent will run without tools until midnight UTC reset."
            )
        else:
            ctx.logger.warning(
                f"Bootstrap failed (API health: {health}): {e}. "
                "Agent will run without tools until MCP recovers."
            )
        ctx.storage.set("tools_metadata", [])


# Register the ASI1 chat protocol with the agent
agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()

import os
import time
import json
import asyncio
import logging
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)

# REST API base URL (for health checks — separate from the MCP endpoint)
_REST_API_BASE = "https://api.ticketlens.com"


# ──────────────────────────────────────────────────────────────────────────────
# Result Enrichment (CDN Injections)
# ──────────────────────────────────────────────────────────────────────────────
def _enrich_with_images(data):
    """
    Recursively injects absolute image URLs wherever an image_id is found.
    Uses the bitmap.ticketlens.com CDN pattern.
    """
    if isinstance(data, list):
        for item in data:
            _enrich_with_images(item)
    elif isinstance(data, dict):
        if "image_id" in data and data["image_id"] is not None:
            # We add a pre-formatted image_url for the LLM to use
            img_id = data["image_id"]
            data["image_url"] = (
                f"https://bitmap.ticketlens.com/image/{img_id}/300x300?returnCrop=yes"
            )

        # Recurse into children
        for val in data.values():
            if isinstance(val, (dict, list)):
                _enrich_with_images(val)
    return data


# Global instance no longer needed as we use persistent ctx.storage
# _cache = _MCPCache()


async def check_api_health() -> str:
    """
    Quickly checks the TicketLens REST API health endpoint.
    Returns 'ok', 'degraded', 'down', or 'rate_limited'.
    Used to give a clearer diagnosis when MCP bootstrap fails with 500.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{_REST_API_BASE}/v1/livez")
            if resp.status_code == 200:
                return "ok"
            if resp.status_code == 429:
                return "rate_limited"
            return "down"
    except Exception:
        return "down"


def _mcp_url() -> str:
    return os.getenv("MCP_SERVER_URL", "https://mcp.ticketlens.com/")


def mcp_to_openai_tool(mcp_tool):
    """
    Maps an MCP tool definition to the OpenAI function-calling schema
    expected by the ASI1 LLM.
    """
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description,
            "parameters": mcp_tool.inputSchema,
        },
    }


async def fetch_mcp_tools(retries: int = 3, backoff: float = 2.0):
    """
    Connects to the remote MCP server via Streamable HTTP transport
    to fetch available tool definitions in OpenAI function-calling format.
    Retries up to `retries` times with exponential backoff on transient errors.

    Note: streamablehttp_client uses asyncio.TaskGroup internally, which raises
    ExceptionGroup (a BaseException subclass) on transport failures. We catch
    BaseException to handle both plain exceptions and ExceptionGroups correctly.
    """
    url = _mcp_url()
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"[MCP] Connecting to {url} (attempt {attempt}/{retries})")
            async with streamablehttp_client(url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    tool_names = [t.name for t in tools_result.tools]
                    logger.info(f"[MCP] Tools loaded: {tool_names}")
                    return [mcp_to_openai_tool(t) for t in tools_result.tools]
        except BaseException as e:  # catches ExceptionGroup from TaskGroup too
            last_error = e
            if attempt < retries:
                wait = backoff * attempt
                logger.warning(
                    f"[MCP] Bootstrap attempt {attempt} failed ({type(e).__name__}): {e}. Retrying in {wait:.0f}s..."
                )
                await asyncio.sleep(wait)
            else:
                logger.error(f"[MCP] All {retries} bootstrap attempts failed.")
    if last_error is not None:
        raise last_error
    raise RuntimeError("Failed to fetch MCP tools")


async def _call_single_tool(sess, tool_call, storage, semaphore):
    """
    Helper to execute a single MCP tool call concurrently.
    Respects the concurrency semaphore to avoid infrastructure-level rate-limit blocks.
    """
    import hashlib

    t_name = tool_call.function.name
    t_args = json.loads(tool_call.function.arguments)

    # 1. Execute with semaphore protection
    async with semaphore:
        logger.info(f"[MCP] [NETWORK] Calling tool '{t_name}'")
        try:
            tool_result = await sess.call_tool(t_name, t_args)

            # 2. Parse and enrich with CDN URLs
            raw_content = ""
            for part in tool_result.content:
                if hasattr(part, "text"):
                    try:
                        json_data = json.loads(part.text)
                        enriched_data = _enrich_with_images(json_data)
                        raw_content += json.dumps(enriched_data, indent=2)
                    except json.JSONDecodeError:
                        raw_content += part.text

            # 3. Calculate TTL based on tool type
            if t_name == "search_pois":
                ttl = 3600  # 1 hour
            elif t_name == "get_tour":
                ttl = 900  # 15 minutes
            else:
                ttl = 300  # 5 minutes

            # 4. Persist to cache
            args_str = json.dumps(t_args, sort_keys=True)
            args_hash = hashlib.md5(args_str.encode()).hexdigest()
            cache_key = f"mcp_cache:{t_name}:{args_hash}"
            storage.set(
                cache_key, {"content": raw_content, "expiry": time.time() + ttl}
            )

            return (tool_call.id, raw_content), 1  # (Result, NetworkCallCount)

        except asyncio.CancelledError:
            # Re-raise cancellation to prevent swallowing task timeouts
            raise
        except BaseException as e:
            logger.error(f"[MCP] Tool call '{t_name}' failed: {e}")
            error_detail = str(e)
            try:
                import re

                match = re.search(r"\{.*\}", error_detail, re.DOTALL)
                if match:
                    error_detail = match.group(0)
            except Exception:
                pass
            return (tool_call.id, f"Error executing {t_name}: {error_detail}"), 1


async def execute_mcp_tools(storage, tool_calls):
    """
    Opens a temporary Streamable HTTP MCP session and executes tool calls in parallel.
    Uses a semaphore to throttle concurrent requests and prevent rate-limit blocks.
    """
    url = _mcp_url()
    final_results = []
    network_call_count = 0

    # 1. Separate calls into 'cached' and 'needed'
    needed_calls = []
    import hashlib

    for tool_call in tool_calls:
        t_name = tool_call.function.name
        try:
            t_args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as err:
            logger.error(f"[MCP] Invalid JSON produced for '{t_name}': {err}")
            final_results.append(
                (
                    tool_call.id,
                    f"Error: Tool argument parsing failed. JSONDecodeError: {err}",
                )
            )
            continue

        args_str = json.dumps(t_args, sort_keys=True)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()
        cache_key = f"mcp_cache:{t_name}:{args_hash}"

        cached_obj = storage.get(cache_key)
        if cached_obj:
            content = cached_obj.get("content")
            expiry = cached_obj.get("expiry", 0)
            if time.time() < expiry:
                logger.info(f"[MCP] [CACHE HIT] Using persistent result for '{t_name}'")
                final_results.append((tool_call.id, content))
                continue
            else:
                storage.set(cache_key, None)  # Lazy cleanup

        needed_calls.append(tool_call)

    # 2. Execute needed calls concurrently
    if needed_calls:
        # Limit to 3 simultaneous calls to avoid TicketLens gateway throttling
        semaphore = asyncio.Semaphore(3)
        async with streamablehttp_client(url) as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()

                # Create concurrent tasks for each tool
                tasks = [
                    _call_single_tool(sess, tc, storage, semaphore)
                    for tc in needed_calls
                ]

                # Execute and collect results
                results = await asyncio.gather(*tasks)

                # Add to final results and track network usage
                for res_tuple, net_count in results:
                    final_results.append(res_tuple)
                    network_call_count += net_count

    return final_results, network_call_count

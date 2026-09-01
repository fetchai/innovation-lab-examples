"""LangChain tools wrapping lastminute MCP."""

import asyncio

from langchain_core.tools import tool

from tripmate.mcp_args import prepare_mcp_args
from tripmate.mcp_client import mcp_client
from tripmate.tool_results import store_tool_result


async def _call_mcp(name: str, args: dict, thread_id: str = "") -> str:
    prepared = prepare_mcp_args(name, args)
    raw = await asyncio.to_thread(mcp_client.call_tool, name, prepared)
    if thread_id:
        store_tool_result(thread_id, name, args, raw)
    return raw


@tool
async def search_flights(
    departure: str,
    arrival: str,
    start_date: str,
    end_date: str = "",
    adults: int = 1,
) -> str:
    """Search flights. Use IATA codes (FCO, MAD). Dates YYYY-MM-DD."""
    from tripmate.graph import _thread_id

    args = {
        "departure": departure,
        "arrival": arrival,
        "start_date": start_date,
        "adults": adults,
    }
    if end_date:
        args["end_date"] = end_date
    return await _call_mcp("search_flights", args, _thread_id.get())


@tool
async def search_only_hotel(
    destination: str,
    date_from: str,
    date_to: str,
    adults: str = "2",
) -> str:
    """Search hotel-only stays. destination=IATA, dates YYYY-MM-DD, adults as string."""
    from tripmate.graph import _thread_id

    return await _call_mcp(
        "search_only_hotel",
        {
            "destination": destination,
            "date_from": date_from,
            "date_to": date_to,
            "adults": adults,
        },
        _thread_id.get(),
    )


@tool
async def search_flight_and_hotel_package(
    origin: str,
    destination: str,
    date_from: str,
    date_to: str,
    adults: str = "2",
) -> str:
    """Search flight+hotel packages. Use IATA codes. date_to = check-out."""
    from tripmate.graph import _thread_id

    return await _call_mcp(
        "search_flight_and_hotel_package",
        {
            "origin": origin,
            "destination": destination,
            "date_from": date_from,
            "date_to": date_to,
            "adults": adults,
        },
        _thread_id.get(),
    )


MCP_LANGCHAIN_TOOLS = [
    search_flights,
    search_only_hotel,
    search_flight_and_hotel_package,
]

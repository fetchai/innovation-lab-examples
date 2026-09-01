"""Thread-local storage for MCP results from LangGraph tool calls."""

_store: dict[str, dict] = {}


def store_tool_result(thread_id: str, tool_name: str, args: dict, raw: str) -> None:
    from tripmate.results import index_search_results
    from tripmate.mcp_args import prepare_mcp_args

    prepared = prepare_mcp_args(tool_name, args)
    _store[thread_id] = {
        "tool": tool_name,
        "args": prepared,
        "raw": raw,
        "index": index_search_results(raw),
    }


def pop_tool_result(thread_id: str) -> dict | None:
    return _store.pop(thread_id, None)

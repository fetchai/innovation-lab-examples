from mcp.server.fastmcp import FastMCP
from src.rag_pipeline import LocalRagEngine

# 1. Initialize the FastMCP server
# This acts as the bridge between your local RAG database and external LLMs like Claude.
mcp = FastMCP("Workspace Context Provider")

# 2. Connect to the exact same RAG Engine our Fetch Agent uses
rag_engine = LocalRagEngine()


# 3. Define the MCP Tool
# The @mcp.tool() decorator tells external LLMs exactly what this function does
# and what arguments it takes, so the LLM can call it autonomously.
@mcp.tool()
def get_workspace_context(query: str, top_k: int = 3) -> str:
    """
    Fetch highly relevant workspace and codebase context.
    Use this tool when you need to understand the user's local code, documentation,
    or architectural decisions.

    Args:
        query: The semantic question to search the codebase for (e.g., "How does authentication work?")
        top_k: Number of context chunks to return (default is 3).
    """
    print(f"[MCP Server] External LLM requested context for: '{query}'")

    # Query our local ChromaDB
    retrieved_context = rag_engine.query_context(query, top_k=top_k)

    return retrieved_context


if __name__ == "__main__":
    print("[MCP Server] Starting stdio server for LLM clients...")
    # MCP servers typically communicate via standard input/output (stdio)
    # so they can be spawned directly as subprocesses by Claude Desktop or Cursor.
    mcp.run_stdio_async()

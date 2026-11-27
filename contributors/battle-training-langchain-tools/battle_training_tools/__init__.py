"""LangChain tools for the battle.training MCP server."""

from .client import BattleTrainingClient, McpError, flatten_result
from .tools import TOOL_SPECS, build_tools

__all__ = [
    "BattleTrainingClient",
    "McpError",
    "flatten_result",
    "TOOL_SPECS",
    "build_tools",
]
__version__ = "0.1.0"

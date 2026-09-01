"""LangGraph ReAct agent for natural-language travel queries."""

import contextvars

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from tripmate.config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL, ASI_ONE_MODEL
from tripmate.prompts import get_system_prompt
from tripmate.tools import MCP_LANGCHAIN_TOOLS

_thread_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "thread_id", default=""
)

_memory = MemorySaver()
_llm = ChatOpenAI(
    model=ASI_ONE_MODEL,
    api_key=ASI_ONE_API_KEY,
    base_url=ASI_ONE_BASE_URL,
    temperature=0,
)


def _dynamic_prompt(state: dict):
    """Inject fresh system prompt (with today's date) on every turn."""
    return [SystemMessage(content=get_system_prompt()), *state["messages"]]


_graph = create_react_agent(
    _llm,
    MCP_LANGCHAIN_TOOLS,
    checkpointer=_memory,
    prompt=_dynamic_prompt,
)


async def run_graph(user_text: str, thread_id: str) -> str:
    _thread_id.set(thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    result = await _graph.ainvoke(
        {"messages": [("user", user_text)]},
        config=config,
    )
    messages = result.get("messages", [])
    if not messages:
        return "How can I help with your trip?"
    last = messages[-1]
    content = getattr(last, "content", last)
    if isinstance(content, list):
        parts = [c.get("text", "") if isinstance(c, dict) else str(c) for c in content]
        return "\n".join(p for p in parts if p) or "Done."
    return str(content)

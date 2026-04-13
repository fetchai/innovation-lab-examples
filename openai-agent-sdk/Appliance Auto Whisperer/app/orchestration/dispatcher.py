from __future__ import annotations

from typing import Any

from app.config import agent_addresses as addr


class Dispatcher:
    """Routes work to named agents (in-process; swap for HTTP/uAgents)."""

    def __init__(self, agents: dict[str, Any]) -> None:
        self._agents = agents

    async def call(self, name: str, **kwargs: Any) -> Any:
        fn = self._agents.get(name)
        if fn is None:
            raise KeyError(f"unknown agent: {name}")
        return await fn(**kwargs)


def default_agent_names() -> tuple[str, ...]:
    return (
        addr.ORCHESTRATOR_AGENT,
        addr.PARTS_SOURCING_AGENT,
        addr.TUTORIAL_AGENT,
        addr.SYNTHESIZER_AGENT,
    )

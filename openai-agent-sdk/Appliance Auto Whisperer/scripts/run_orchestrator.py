"""CLI: run full orchestrator once."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.orchestrator_agent import OrchestratorAgent  # noqa: E402
from app.models.messages import ChatRequest  # noqa: E402


async def main() -> None:
    appliance = sys.argv[1] if len(sys.argv) > 1 else "dryer"
    symptoms = sys.argv[2] if len(sys.argv) > 2 else "won't start"
    orch = OrchestratorAgent()
    syn, structured = await orch.run(
        ChatRequest(appliance_type=appliance, symptoms=symptoms),
        correlation_id="cli",
    )
    print(
        json.dumps(
            {"synthesis": syn.model_dump(), "structured": structured},
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())

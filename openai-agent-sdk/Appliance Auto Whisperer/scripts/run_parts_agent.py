"""CLI: run parts sourcing agent."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.parts_sourcing_agent import run_parts_sourcing  # noqa: E402
from app.models.diagnosis import DiagnosisPayload  # noqa: E402
from app.models.messages import ChatRequest  # noqa: E402


async def main() -> None:
    req = ChatRequest(
        appliance_type=sys.argv[1] if len(sys.argv) > 1 else "oven",
        symptoms=sys.argv[2] if len(sys.argv) > 2 else "won't heat",
    )
    diag = DiagnosisPayload(suggested_parts=["bake element"])
    out = await run_parts_sourcing(req, diag)
    print(json.dumps(out.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())

"""CLI: run tutorial agent."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.tutorial_agent import run_tutorial  # noqa: E402
from app.models.diagnosis import DiagnosisPayload  # noqa: E402
from app.models.messages import ChatRequest  # noqa: E402


async def main() -> None:
    req = ChatRequest(
        appliance_type=sys.argv[1] if len(sys.argv) > 1 else "washer",
        symptoms=sys.argv[2] if len(sys.argv) > 2 else "loud spin",
    )
    diag = DiagnosisPayload()
    out = await run_tutorial(req, diag)
    print(json.dumps([v.model_dump() for v in out], indent=2))


if __name__ == "__main__":
    asyncio.run(main())

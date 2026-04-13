"""CLI: run synthesizer with dummy upstream data."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.synthesizer_agent import run_synthesizer  # noqa: E402
from app.models.diagnosis import DiagnosisPayload  # noqa: E402
from app.models.messages import ChatRequest  # noqa: E402
from app.models.sourcing import SourcingResult  # noqa: E402
from app.models.tutorial import VideoHit  # noqa: E402


async def main() -> None:
    req = ChatRequest(appliance_type="microwave", symptoms="sparks")
    diag = DiagnosisPayload(
        summary="Waveguide cover damage possible.", suggested_parts=["waveguide cover"]
    )
    src = SourcingResult()
    vids = [VideoHit(title="Fix arcing", video_id="abc", url="https://youtu.be/abc")]
    out = await run_synthesizer(req, diag, src, vids)
    print(json.dumps(out.model_dump(), indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

from app.models.diagnosis import DiagnosisPayload
from app.models.messages import ChatRequest
from app.models.sourcing import SourcingResult
from app.models.synthesis import SynthesisResult
from app.models.tutorial import VideoHit
from app.services.pricing.heuristics import rough_part_cost_band


async def run_synthesizer(
    req: ChatRequest,
    diagnosis: DiagnosisPayload,
    sourcing: SourcingResult,
    videos: list[VideoHit],
) -> SynthesisResult:
    _ = (req, sourcing, videos)
    n = max(1, len(diagnosis.suggested_parts))
    low, high = rough_part_cost_band(n)
    return SynthesisResult(
        summary=diagnosis.summary or "See diagnosis and videos.",
        next_steps=[
            "Confirm model/serial and verify parts fit.",
            "Review safety notes before disassembly.",
        ],
        estimated_cost_range=(low, high),
        raw={"parts_considered": n},
    )

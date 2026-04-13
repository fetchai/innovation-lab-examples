from __future__ import annotations

from app.models.diagnosis import DiagnosisPayload
from app.models.messages import ChatRequest
from app.models.tutorial import VideoHit
from app.services.youtube.client import search_repair_videos


async def run_tutorial(req: ChatRequest, diagnosis: DiagnosisPayload) -> list[VideoHit]:
    _ = diagnosis
    return await search_repair_videos(req.appliance_type, req.symptoms, max_results=5)

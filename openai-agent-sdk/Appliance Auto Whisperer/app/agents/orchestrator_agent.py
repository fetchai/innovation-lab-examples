from __future__ import annotations

from typing import Any

from app.agents.parts_sourcing_agent import run_parts_sourcing
from app.agents.synthesizer_agent import run_synthesizer
from app.agents.tutorial_agent import run_tutorial
from app.models.messages import ChatRequest
from app.models.synthesis import SynthesisResult
from app.orchestration.aggregator import merge_structured
from app.services.openai.diagnosis_client import diagnose_symptoms


class OrchestratorAgent:
    async def run(
        self, req: ChatRequest, *, correlation_id: str
    ) -> tuple[SynthesisResult, dict[str, Any]]:
        _ = correlation_id
        diagnosis = await diagnose_symptoms(
            req.symptoms,
            req.appliance_type,
            image_base64=req.image_base64,
        )
        sourcing = await run_parts_sourcing(req, diagnosis)
        tutorials = await run_tutorial(req, diagnosis)
        syn = await run_synthesizer(req, diagnosis, sourcing, tutorials)
        structured = merge_structured(
            diagnosis.model_dump(),
            sourcing.model_dump(),
            {"videos": [v.model_dump() for v in tutorials]},
            syn.model_dump(),
        )
        return syn, structured

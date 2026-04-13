import pytest

from app.agents.synthesizer_agent import run_synthesizer
from app.models.diagnosis import DiagnosisPayload
from app.models.messages import ChatRequest
from app.models.sourcing import SourcingResult


@pytest.mark.asyncio
async def test_synthesizer() -> None:
    req = ChatRequest(appliance_type="fridge", symptoms="warm")
    diag = DiagnosisPayload(summary="Evap fan?", suggested_parts=["fan"])
    syn = await run_synthesizer(req, diag, SourcingResult(), [])
    assert syn.estimated_cost_range

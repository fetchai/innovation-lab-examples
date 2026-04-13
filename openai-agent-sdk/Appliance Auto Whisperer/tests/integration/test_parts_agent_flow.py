import pytest

from app.agents.parts_sourcing_agent import run_parts_sourcing
from app.models.diagnosis import DiagnosisPayload
from app.models.messages import ChatRequest


@pytest.mark.asyncio
async def test_parts_sourcing_stub() -> None:
    req = ChatRequest(appliance_type="dryer", symptoms="noise")
    diag = DiagnosisPayload(suggested_parts=["belt"])
    out = await run_parts_sourcing(req, diag)
    assert out.offers

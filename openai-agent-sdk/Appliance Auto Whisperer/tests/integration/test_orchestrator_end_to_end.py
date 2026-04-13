import pytest

from app.agents.orchestrator_agent import OrchestratorAgent
from app.models.messages import ChatRequest


@pytest.mark.asyncio
async def test_orchestrator_agent_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    from app.config.settings import get_settings

    get_settings.cache_clear()
    orch = OrchestratorAgent()
    syn, structured = await orch.run(
        ChatRequest(appliance_type="oven", symptoms="no heat"),
        correlation_id="t",
    )
    assert syn.summary
    assert "diagnosis" in structured
    get_settings.cache_clear()

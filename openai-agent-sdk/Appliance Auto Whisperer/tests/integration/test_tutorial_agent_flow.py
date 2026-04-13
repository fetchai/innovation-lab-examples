import pytest

from app.agents.tutorial_agent import run_tutorial
from app.models.diagnosis import DiagnosisPayload
from app.models.messages import ChatRequest


@pytest.mark.asyncio
async def test_tutorial_empty_without_youtube_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    from app.config.settings import get_settings

    get_settings.cache_clear()
    req = ChatRequest(appliance_type="washer", symptoms="spin")
    out = await run_tutorial(req, DiagnosisPayload())
    assert out == []
    get_settings.cache_clear()

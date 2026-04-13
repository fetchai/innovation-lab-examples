import pytest

from app.services.openai.diagnosis_client import diagnose_symptoms


@pytest.mark.asyncio
async def test_diagnose_fallback_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.config.settings import get_settings

    get_settings.cache_clear()
    d = await diagnose_symptoms("leak", "dishwasher")
    assert d.summary
    get_settings.cache_clear()

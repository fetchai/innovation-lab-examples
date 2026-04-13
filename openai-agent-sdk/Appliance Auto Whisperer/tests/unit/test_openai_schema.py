from app.services.openai.schema import normalize_diagnosis_dict


def test_normalize_diagnosis_dict() -> None:
    raw = {"summary": "s", "likely_causes": ["a"], "extra": 1}
    out = normalize_diagnosis_dict(raw)
    assert out["summary"] == "s"
    assert "likely_causes" in out

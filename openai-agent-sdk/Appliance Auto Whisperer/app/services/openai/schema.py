"""JSON shapes expected from diagnosis LLM output."""

DIAGNOSIS_JSON_KEYS = frozenset(
    {"summary", "likely_causes", "suggested_parts", "safety_notes"},
)


def normalize_diagnosis_dict(raw: dict) -> dict:
    out = {k: raw.get(k) for k in DIAGNOSIS_JSON_KEYS if k in raw}
    if "summary" not in out:
        out["summary"] = str(raw.get("summary") or "")
    if "likely_causes" not in out:
        out["likely_causes"] = raw.get("likely_causes") or []
    if "suggested_parts" not in out:
        out["suggested_parts"] = raw.get("suggested_parts") or []
    if "safety_notes" not in out:
        out["safety_notes"] = raw.get("safety_notes") or []
    return out

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.config.settings import get_settings
from app.models.diagnosis import DiagnosisPayload
from app.services.openai.prompt_builder import synthesis_style
from app.services.openai.schema import normalize_diagnosis_dict
from app.utils.json_utils import safe_json_loads


async def diagnose_symptoms(
    symptoms: str,
    appliance_type: str,
    *,
    image_base64: str | None = None,
) -> DiagnosisPayload:
    settings = get_settings()
    system = (
        "You are an appliance repair assistant. Respond as JSON with keys: "
        "summary (string), likely_causes (list of strings), "
        "suggested_parts (list of strings), safety_notes (list of strings).\n"
        f"Style: {synthesis_style()[:500]}"
    )
    user = f"Appliance: {appliance_type}\nSymptoms: {symptoms}"
    if not settings.openai_api_key:
        return _fallback(appliance_type, symptoms)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if image_base64:
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Image attached for visual diagnosis context.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ],
            }
        )

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2,
    )
    content = resp.choices[0].message.content or "{}"
    try:
        raw = safe_json_loads(content)
        raw = normalize_diagnosis_dict(raw)
        return DiagnosisPayload(
            summary=str(raw.get("summary", "")),
            likely_causes=list(raw.get("likely_causes") or []),
            suggested_parts=list(raw.get("suggested_parts") or []),
            safety_notes=list(raw.get("safety_notes") or []),
            raw=raw,
        )
    except Exception:
        return _fallback(appliance_type, symptoms)


def _fallback(appliance_type: str, symptoms: str) -> DiagnosisPayload:
    return DiagnosisPayload(
        summary=f"Offline placeholder for {appliance_type}: {symptoms[:120]}",
        likely_causes=[],
        suggested_parts=[],
        safety_notes=["Unplug before inspection when applicable."],
        raw={},
    )

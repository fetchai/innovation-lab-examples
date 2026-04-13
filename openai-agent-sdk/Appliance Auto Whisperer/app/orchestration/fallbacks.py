from app.models.diagnosis import DiagnosisPayload


def diagnosis_fallback(appliance_type: str, symptoms: str) -> DiagnosisPayload:
    return DiagnosisPayload(
        summary=f"Fallback diagnosis for {appliance_type}",
        likely_causes=["Unknown without model output"],
        suggested_parts=[],
        safety_notes=["Verify power and water supply where applicable."],
        raw={},
    )

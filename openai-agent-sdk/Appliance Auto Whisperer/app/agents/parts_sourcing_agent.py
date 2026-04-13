from __future__ import annotations

from app.models.diagnosis import DiagnosisPayload
from app.models.messages import ChatRequest
from app.models.sourcing import PartOffer, SourcingResult
from app.services.brightdata.normalizer import normalize_part_label
from app.services.brightdata.search_builder import build_parts_query


async def run_parts_sourcing(
    req: ChatRequest, diagnosis: DiagnosisPayload
) -> SourcingResult:
    parts = [normalize_part_label(p) for p in diagnosis.suggested_parts[:5]]
    if not parts and req.symptoms:
        parts = [normalize_part_label(req.symptoms)[:80]]
    offers: list[PartOffer] = []
    queries: list[str] = []
    for p in parts:
        q = build_parts_query(req.appliance_type, p)
        queries.append(q)
        offers.append(
            PartOffer(
                title=f"{p} — see search query in sourcing.notes",
                url="",
                vendor="search",
                price_hint=None,
            ),
        )
    note = "; ".join(queries[:3]) if queries else "No part candidates"
    return SourcingResult(query=req.appliance_type, offers=offers, notes=note)

"""
Vision LLM — strict JSON extraction from a photo + appliance/vehicle model string.

Provider priority (configurable via VISION_PROVIDER in .env):
  auto   → Gemini Flash if GEMINI_API_KEY set, else OpenAI if OPENAI_API_KEY set
  gemini → Google Gemini 2.0 Flash  (free tier: 1500 req/day, ~$0.0001/image paid)
  openai → OpenAI GPT-4o            (paid only,  ~$0.005/image)

Both providers are accessed via the OpenAI Python SDK using different base_url values.
Gemini's OpenAI-compatible endpoint: https://generativelanguage.googleapis.com/v1beta/openai/
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config.settings import get_settings
from app.services.media.base64_utils import strip_data_url
from app.utils.json_utils import safe_json_loads

log = logging.getLogger(__name__)

# ── Provider configs ──────────────────────────────────────────────────────────

_PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        # Model names via this endpoint require the "models/" prefix.
        # models/gemini-2.0-flash-lite — free tier, fast, multimodal vision support.
        # Override with GEMINI_MODEL env var, e.g. GEMINI_MODEL=models/gemini-2.5-flash
        "model": "models/gemini-2.0-flash-lite",
        "supports_json_mode": True,
    },
    "openai": {
        "base_url": None,  # default OpenAI endpoint
        "model": "gpt-4o",
        "supports_json_mode": True,
    },
}

# ── System prompt ─────────────────────────────────────────────────────────────

VISION_SYSTEM = """You are an expert appliance and automotive parts identifier.
The user provides a photo and a model/context string (e.g. appliance model or vehicle).

Output ONLY a JSON object with exactly these keys:
- "part_name": string — the specific failed component (e.g. "Evaporator Fan Motor")
- "part_number": string — OEM part number if visible, or best-effort estimate (e.g. "W10312696")
- "brand": string — manufacturer/brand of the appliance or vehicle (e.g. "GE", "Whirlpool", "Samsung", "Toyota"). Extract from the user's context text if mentioned.
- "model_number": string — model number of the appliance or vehicle if mentioned by the user (e.g. "PYE22KBLCTS"). Empty string if not provided.
- "appliance_type": string — type of appliance or vehicle (e.g. "refrigerator", "dishwasher", "washing machine", "car"). Infer from context and image.
- "estimated_labor_cost": number (USD) — typical technician call-out in a high-cost US metro (San Jose CA baseline)
- "confidence": number between 0 and 1 — how certain you are about the part identification
- "issue_summary": string — one short sentence describing the likely failure

No markdown fences, no extra keys, no extra text. Pure JSON only."""


# ── Main entry point ──────────────────────────────────────────────────────────


async def extract_part_diagnosis(
    image_base64: str, context_text: str
) -> dict[str, Any]:
    """
    Call the configured Vision LLM with the image and appliance/vehicle context.
    Returns a normalized dict with: part_name, part_number, estimated_labor_cost,
    confidence, issue_summary, context_text.
    """
    settings = get_settings()
    provider = settings.active_vision_provider

    if not provider:
        log.warning(
            "No vision API key configured. Set GEMINI_API_KEY (free) in .env. "
            "Returning stub diagnosis."
        )
        return normalize_diagnosis(
            {
                "part_name": "Unidentified part",
                "part_number": "UNKNOWN",
                "estimated_labor_cost": 250.0,
                "confidence": 0.0,
                "issue_summary": "Vision unavailable — set GEMINI_API_KEY for free AI diagnosis.",
            },
            context_text,
        )

    cfg = dict(_PROVIDERS[provider])  # type: ignore[call-overload]  # copy so we can override model
    # Use model from Settings (read from .env via pydantic-settings)
    if provider == "gemini":
        cfg["model"] = settings.gemini_model
        api_key = settings.gemini_api_key
    else:
        cfg["model"] = settings.openai_vision_model
        api_key = settings.openai_api_key
    log.info("[vision] Using provider=%s model=%s", provider, cfg["model"])

    b64 = strip_data_url(image_base64)
    user_text = (
        f"Context / model identifier:\n{context_text}\n\n"
        "Identify the failed part and estimate repair labor cost."
    )

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if cfg["base_url"]:
        client_kwargs["base_url"] = cfg["base_url"]

    client = AsyncOpenAI(**client_kwargs)

    try:
        create_kwargs: dict[str, Any] = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": VISION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                },
            ],
            "temperature": 0.1,
        }
        if cfg["supports_json_mode"]:
            create_kwargs["response_format"] = {"type": "json_object"}

        resp = await client.chat.completions.create(**create_kwargs)
        raw = resp.choices[0].message.content or "{}"
        log.debug("[vision] Raw response: %s", raw[:300])

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = safe_json_loads(raw)

    except Exception as exc:
        log.error("[vision] %s call failed: %s", provider, exc)
        return normalize_diagnosis(
            {
                "part_name": "Unidentified part",
                "part_number": "UNKNOWN",
                "estimated_labor_cost": 250.0,
                "confidence": 0.0,
                "issue_summary": f"Vision request failed ({provider}): {type(exc).__name__}",
            },
            context_text,
        )

    return normalize_diagnosis(data, context_text)


# ── Normalisation + validation ────────────────────────────────────────────────


def normalize_diagnosis(data: dict[str, Any], context_text: str) -> dict[str, Any]:
    """Coerce LLM output into well-typed fields with safe defaults."""
    part_name = str(data.get("part_name") or "").strip() or "Unknown part"
    part_number = str(data.get("part_number") or "").strip() or "UNKNOWN"
    brand = str(data.get("brand") or "").strip()
    model_number = str(data.get("model_number") or "").strip()
    appliance_type = str(data.get("appliance_type") or "").strip()

    labor = data.get("estimated_labor_cost")
    try:
        est = float(labor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        est = 250.0
    if est < 0:
        est = 250.0

    conf = data.get("confidence")
    try:
        c = float(conf)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        c = 0.5
    c = max(0.0, min(1.0, c))

    summary = str(data.get("issue_summary") or "").strip()

    return {
        "part_name": part_name,
        "part_number": part_number,
        "brand": brand,
        "model_number": model_number,
        "appliance_type": appliance_type,
        "estimated_labor_cost": est,
        "confidence": c,
        "issue_summary": summary,
        "context_text": context_text,
    }


def validate_diagnosis(d: dict[str, Any]) -> str | None:
    """Return an error message if the diagnosis is unusable, else None."""
    if not d.get("part_name") or d.get("part_name") == "Unknown part":
        return "Could not identify a specific part from the image"
    if not d.get("part_number") or d.get("part_number") == "UNKNOWN":
        return "Could not determine a part number — try a clearer photo"
    return None

"""
RSC payload parsing and ASI:One LLM extraction utilities.

Cerebral Valley uses Next.js RSC. The full event data is embedded as escaped
JSON strings inside <script>self.__next_f.push(...)</script> tags — the rendered
HTML itself is nearly empty. We unescape and search those script payloads for data.
"""

import re
import json
import httpx
from typing import Any

from config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL, ASI_ONE_MODEL


def parse_rsc_payload(html: str) -> str:
    """Extract and unescape all RSC script payload text from a Next.js HTML page."""
    chunks = re.findall(
        r'self\.__next_f\.push\(\[1,\s*"(.*?)"\]\)',
        html,
        re.DOTALL,
    )
    combined = " ".join(chunks)
    # Unescape the JSON string encoding
    combined = combined.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
    return combined


def extract_event_json_from_rsc(rsc_text: str) -> dict | None:
    """
    Parse the full platform event envelope from the RSC payload.
    The structure is:
      {"detail":..., "userRoles":[], "event":{...fields..., "startDateTime":...},
       "hosts":[...], "questions":[...], "media":[...]}

    We anchor on "startDateTime", walk out to the parent envelope object,
    then parse it whole so hosts/questions/media are included.
    Returns a flat merged dict: event fields + hosts + questions + media, or None.
    """
    idx = rsc_text.find('"startDateTime"')
    if idx == -1:
        return None

    # Find the opening brace of the inner event object
    inner_start = rsc_text.rfind("{", 0, idx)
    if inner_start == -1:
        return None

    # Walk further back to find the parent envelope object
    # The envelope contains "event":{...} so look for the brace before "event":
    envelope_start = rsc_text.rfind("{", 0, inner_start - 1)
    if envelope_start == -1:
        envelope_start = inner_start

    # Walk forward from envelope_start to find its matching close brace
    depth = 0
    end = envelope_start
    for i, ch in enumerate(rsc_text[envelope_start:], start=envelope_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    try:
        envelope = json.loads(rsc_text[envelope_start:end])
    except json.JSONDecodeError:
        # Fall back to just the inner event object
        depth = 0
        end = inner_start
        for i, ch in enumerate(rsc_text[inner_start:], start=inner_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        try:
            return json.loads(rsc_text[inner_start:end])
        except json.JSONDecodeError:
            return None

    # Flatten: merge the inner "event" dict with top-level hosts/questions/media
    inner = envelope.get("event", {})
    if isinstance(inner, dict):
        merged = {**inner}
        for key in ("hosts", "questions", "media"):
            if key in envelope and envelope[key]:
                merged[key] = envelope[key]
        return merged

    return envelope


def get_event_data_slice(rsc_text: str, window: int = 6000) -> str:
    """
    Return a focused slice of RSC text centred around the event data
    (near 'startDateTime') for passing to the LLM.
    """
    idx = rsc_text.find('"startDateTime"')
    if idx == -1:
        # Fallback: just return the last portion which usually has the event data
        return rsc_text[-window:]
    start = max(0, idx - window // 2)
    return rsc_text[start : start + window]


def extract_event_urls_from_rsc(rsc_text: str, base_url: str) -> list[dict]:
    """
    Extract event slugs and URLs from a listing page RSC payload.
    Returns list of {slug, url} dicts.
    """
    slugs = set(re.findall(r'"slug"\s*:\s*"([a-z0-9\-]+)"', rsc_text))
    # Also find /e/<slug> links
    link_slugs = set(re.findall(r'href["\s:]+/e/([a-z0-9\-]+)', rsc_text))
    all_slugs = slugs | link_slugs

    return [
        {"slug": s, "url": f"{base_url}/e/{s}"}
        for s in sorted(all_slugs)
        if s  # skip empty
    ]


def llm_extract(text: str, instruction: str) -> dict | list:
    """
    Call ASI:One with the given text and instruction.
    Returns parsed JSON (dict or list). Falls back to empty dict on failure.
    """
    payload = {
        "model": ASI_ONE_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a data extraction assistant. Extract structured information and return valid JSON only — no markdown, no explanation.",
            },
            {
                "role": "user",
                "content": f"{instruction}\n\nContent:\n{text[:8000]}",
            },
        ],
        "max_tokens": 2000,
        "temperature": 0,
    }

    try:
        response = httpx.post(
            f"{ASI_ONE_BASE_URL}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}"},
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if present
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        return json.loads(content)
    except Exception as e:
        print(f"  [LLM] extraction failed: {e}")
        return {}


def llm_extract_event_urls(rsc_text: str, base_url: str) -> list[dict]:
    """Use ASI:One to extract event slugs from a listing page when regex misses some."""
    instruction = (
        "Extract all hackathon event slugs and their full URLs from this page content. "
        f"All URLs follow the pattern {base_url}/e/<slug>. "
        'Return a JSON array of objects like: [{"slug": "...", "url": "..."}]'
    )
    result = llm_extract(rsc_text[:6000], instruction)
    if isinstance(result, list):
        return result
    return []


def llm_extract_event_details(rsc_text: str) -> dict[str, Any]:
    """Use ASI:One to extract/validate event details from an event page RSC payload."""
    instruction = (
        "Extract hackathon event details from this raw page data. "
        "Return a JSON object with these fields (use null for missing): "
        "title, date_start (ISO8601), date_end (ISO8601), timezone, city, "
        "description, description_summary, prize_amount, registration_open (bool), "
        "approval_required (bool), capacity, organizer_name, organizer_handle, "
        "image_url, tags (array of strings), extra (any other relevant fields as object)."
    )
    result = llm_extract(rsc_text, instruction)
    return result if isinstance(result, dict) else {}

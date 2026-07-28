"""
Crawl a single hackathon event page and return a structured event dict
ready to be upserted into Supabase.

Strategy:
1. Fetch raw HTML via crawl4ai (returns full crawl result, not just HTML)
2. Parse RSC payload
3. Direct JSON extraction from the RSC payload (most reliable for known fields)
4. ASI:One LLM pass to fill in any gaps / validate
5. Detect external registration URLs (Luma, Eventbrite, Devpost, etc.)
6. If found, crawl the external page and merge its data
7. Return normalised event dict
"""

import httpx
from typing import Any

from config import CRAWL4AI_BASE
from extract import (
    parse_rsc_payload,
    extract_event_json_from_rsc,
    get_event_data_slice,
    llm_extract_event_details,
)
from crawl_external import detect_external_url, crawl_external


def crawl_event(source: str, slug: str, url: str) -> dict[str, Any] | None:
    """
    Crawl one event page. Returns a normalised event dict or None on failure.
    """
    print(f"  [CRAWL] → {url}")

    crawl_result = _fetch_result(url)
    if not crawl_result:
        print(f"  [CRAWL] no result returned for {url}")
        return None

    html = crawl_result.get("html", "")
    rsc_text = parse_rsc_payload(html)

    # --- Direct JSON extraction (fast, reliable for platform-standard fields) ---
    platform_data = extract_event_json_from_rsc(rsc_text)

    # --- LLM extraction: pass a focused slice around the event data ---
    event_slice = get_event_data_slice(rsc_text)
    llm_data = llm_extract_event_details(event_slice)
    print(
        f"  [EXTRACT] ✓ (platform_fields={len(platform_data or {})}, llm_fields={len(llm_data)})"
    )

    # --- External platform crawl (Luma, Eventbrite, Devpost, etc.) ---
    external_data: dict | None = None
    external_url: str | None = None
    external_source: str | None = None

    ext_match = detect_external_url(crawl_result, rsc_text)
    if ext_match:
        external_url, external_source = ext_match
        external_data = crawl_external(external_url, external_source)

    # --- Merge: platform data is authoritative, llm fills gaps ---
    event = _merge_event(
        source,
        slug,
        url,
        platform_data or {},
        llm_data,
        external_url=external_url,
        external_source=external_source,
        external_data=external_data,
    )
    return event


def _fetch_result(url: str) -> dict | None:
    """POST to crawl4ai and return the full result object (not just HTML)."""
    try:
        resp = httpx.post(
            f"{CRAWL4AI_BASE}/crawl",
            json={"urls": [url]},
            timeout=60,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"  [CRAWL] fetch error for {url}: {e}")
        return None


def _merge_event(
    source: str,
    slug: str,
    url: str,
    platform: dict[str, Any],
    llm: dict[str, Any],
    external_url: str | None = None,
    external_source: str | None = None,
    external_data: dict | None = None,
) -> dict[str, Any]:
    """
    Build a normalised event row by combining platform JSON and LLM output.
    Platform fields take precedence.
    """
    # Extract nested objects from platform data
    hosts = platform.get("hosts") or []
    questions = platform.get("questions") or []
    media = platform.get("media") or []
    image_url = (
        media[0].get("url")
        if media and isinstance(media, list) and media[0].get("url")
        else llm.get("image_url")
    )

    event: dict[str, Any] = {
        # Identity
        "id": platform.get("id") or f"{source}:{slug}",
        "source": source,
        "slug": platform.get("slug") or slug,
        "event_url": url,
        # Core info (platform authoritative)
        "title": platform.get("title") or llm.get("title"),
        "description": _get_description(platform) or llm.get("description"),
        "description_summary": platform.get("descriptionSummary")
        or llm.get("description_summary"),
        # Timing
        "start_datetime": platform.get("startDateTime") or llm.get("date_start"),
        "end_datetime": platform.get("endDateTime") or llm.get("date_end"),
        "timezone": platform.get("timeZone") or llm.get("timezone"),
        # Location
        "city": platform.get("city") or llm.get("city"),
        "city_latitude": platform.get("cityLatitude"),
        "city_longitude": platform.get("cityLongitude"),
        # Config flags
        "event_type": platform.get("type") or llm.get("event_type"),
        "capacity": platform.get("capacity") or llm.get("capacity"),
        "is_platform_hackathon": platform.get("isPlatformHackathon"),
        "searchable": platform.get("searchable"),
        "approval_required": platform.get("approvalRequired")
        or llm.get("approval_required"),
        "registration_closed": platform.get("registrationClosed"),
        "enable_chat_apply": platform.get("enableChatApply"),
        "hide_guest_list": platform.get("hideGuestList"),
        "show_guest_list_before_approval": platform.get("showGuestListBeforeApproval"),
        "show_location_before_approval": platform.get("showLocationBeforeApproval"),
        "hackathon_public_voting_enabled": platform.get("hackathonPublicVotingEnabled"),
        "show_hackathon_gallery": platform.get("showHackathonGallery"),
        "hackathon_judging_open": platform.get("hackathonJudgingOpen"),
        "auto_scoring_enabled": platform.get("autoScoringEnabled"),
        # Nested JSONB
        "hosts": hosts,
        "questions": questions,
        "media": media,
        "image_url": image_url,
        # LLM extras stored for future use
        "llm_extracted": {
            k: v
            for k, v in llm.items()
            if k
            not in {
                "title",
                "description",
                "description_summary",
                "date_start",
                "date_end",
                "timezone",
                "city",
                "approval_required",
                "capacity",
                "image_url",
            }
        },
        # External platform data
        "external_url": external_url,
        "external_source": external_source,
        "external_data": external_data,
        # Platform timestamps
        "platform_created_at": platform.get("createdAt"),
        "platform_updated_at": platform.get("updatedAt"),
    }

    return event


def _get_description(platform: dict) -> str | None:
    """Extract plain text description from platform data (may be a rich text ref)."""
    desc = platform.get("description")
    # If it's a reference string like "$2b", it's a RSC reference — skip
    if isinstance(desc, str) and desc.startswith("$"):
        return None
    return desc

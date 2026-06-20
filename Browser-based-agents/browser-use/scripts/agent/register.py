"""
Registration agent — main entry point.

Looks up the event, generates answers to its questions using the
user's profile + ASI:One, then delegates to the right platform
handler to drive the browser and complete registration.

Usage:
    import asyncio
    from agent.register import register_for_event
    from agent.profile import load_profile

    profile = load_profile()
    result = asyncio.run(register_for_event("aiewf-hackathon-2026", profile))
    print(result)

CLI:
    python scripts/agent/register.py --event aiewf-hackathon-2026
    python scripts/agent/register.py --url https://lu.ma/some-hackathon
"""

import asyncio
import json
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from playwright.async_api import async_playwright
from agent.profile import UserProfile, load_profile
from agent.answer_gen import generate_answers
from db import get_client


# Platform routing — maps external_source → handler module name
PLATFORM_HANDLERS = {
    "cerebralvalley": "cerebralvalley",   # dedicated Playwright handler
    # everything else → generic browser-use handler
}

# Platforms that require login (warn user)
LOGIN_REQUIRED = {"cerebralvalley", "devpost"}

# Platforms that use magic link (just need email)
MAGIC_LINK_PLATFORMS = {"luma", "partiful"}


async def register_for_event(
    slug: str | None = None,
    url: str | None = None,
    profile: UserProfile | None = None,
    headless: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Register a user for a hackathon.

    Args:
        slug        : event slug from our DB (looks up event automatically)
        url         : direct registration URL (skips DB lookup)
        profile     : UserProfile (loads from ~/.hackathon_profile.json if None)
        headless    : run browser headlessly (default False — show browser)
        dry_run     : generate answers but don't open browser

    Returns dict with: success, message, event_title, answers_preview
    """
    if profile is None:
        profile = load_profile()

    # Step 1: load event from DB
    event = _load_event(slug=slug, url=url)
    if not event and not url:
        return {"success": False, "message": f"Event not found: {slug or url}"}

    event_url    = url or event.get("external_url") or event.get("event_url", "")
    event_title  = event.get("title", "") if event else ""
    event_desc   = event.get("description_summary", "") if event else ""
    ext_source   = (event.get("external_source") if event else None) or _detect_platform(event_url)
    questions    = _parse_questions(event.get("questions") if event else None)

    print(f"\n[REGISTER] Event:    {event_title or event_url}")
    print(f"[REGISTER] Platform: {ext_source}")
    print(f"[REGISTER] URL:      {event_url}")
    print(f"[REGISTER] Questions: {len(questions)}")

    # Warn about login requirements
    if ext_source in LOGIN_REQUIRED and not _has_login(profile, ext_source):
        print(f"\n  ⚠️  {ext_source} requires login. Add credentials to your profile:")
        print(f"     profile.{ext_source}_email and profile.{ext_source}_password")

    # Step 2: generate answers
    print(f"\n[REGISTER] Generating answers with ASI:One...")
    answers = generate_answers(questions, profile, event_title, event_desc)

    print(f"\n[REGISTER] Answers preview:")
    for q, a in answers.items():
        print(f"  Q: {q[:60]}")
        print(f"  A: {a[:80]}\n")

    if dry_run:
        return {
            "success": True,
            "message": "Dry run — answers generated, browser not opened",
            "event_title": event_title,
            "event_url": event_url,
            "answers_preview": answers,
        }

    if not event_url:
        return {"success": False, "message": "No registration URL found for this event"}

    # Step 3: open browser and register
    print(f"\n[REGISTER] Opening browser...")
    result = await _run_browser(
        event_url=event_url,
        event_title=event_title,
        ext_source=ext_source,
        profile=profile,
        answers=answers,
        headless=headless,
    )

    result["event_title"] = event_title
    result["event_url"] = event_url
    result["answers_preview"] = answers

    status = "✅ Success" if result.get("success") else "❌ Failed"
    print(f"\n[REGISTER] {status}: {result.get('message','')}")

    return result


async def _run_browser(
    event_url: str,
    event_title: str,
    ext_source: str,
    profile: UserProfile,
    answers: dict,
    headless: bool,
) -> dict:
    """Route to the right platform handler."""

    # Dedicated Playwright handler for Cerebral Valley
    if ext_source == "cerebralvalley" or "cerebralvalley.ai" in event_url:
        from agent.platforms.cerebralvalley import register as cv_register
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless)
            page = await browser.new_page()
            try:
                return await cv_register(page, event_url, profile, answers)
            finally:
                await browser.close()

    # Generic browser-use handler for all other platforms
    from agent.platforms.generic import register as generic_register
    return await generic_register(
        event_url=event_url,
        profile=profile,
        answers=answers,
        event_title=event_title,
        headless=headless,
    )


def _load_event(slug: str | None, url: str | None) -> dict | None:
    """Load event from Supabase by slug or URL."""
    client = get_client()
    try:
        if slug:
            rows = client.table("events").select("*").eq("slug", slug).limit(1).execute().data
        elif url:
            rows = client.table("events").select("*").eq("external_url", url).limit(1).execute().data
            if not rows:
                rows = client.table("events").select("*").eq("event_url", url).limit(1).execute().data
        else:
            return None
        return rows[0] if rows else None
    except Exception as e:
        print(f"  [REGISTER] DB lookup failed: {e}")
        return None


def _parse_questions(questions_raw) -> list[dict]:
    """Parse questions from DB (may be JSON string or list)."""
    if not questions_raw:
        return []
    if isinstance(questions_raw, list):
        return questions_raw
    if isinstance(questions_raw, str):
        try:
            return json.loads(questions_raw)
        except Exception:
            return []
    return []


def _detect_platform(url: str) -> str:
    """Detect platform from URL."""
    url_lower = url.lower()
    for domain, name in [
        ("cerebralvalley.ai", "cerebralvalley"),
        ("lu.ma", "luma"),
        ("eventbrite.com", "eventbrite"),
        ("devpost.com", "devpost"),
        ("devfolio.co", "devfolio"),
        ("dorahacks.io", "dorahacks"),
        ("partiful.com", "partiful"),
        ("ethglobal.com", "ethglobal"),
    ]:
        if domain in url_lower:
            return name
    return "external"


def _has_login(profile: UserProfile, platform: str) -> bool:
    """Check if profile has credentials for a platform."""
    if platform == "cerebralvalley":
        return bool(profile.cerebralvalley_email)
    if platform == "devpost":
        return bool(profile.devpost_email)
    return True


def main():
    parser = argparse.ArgumentParser(description="Register for a hackathon")
    parser.add_argument("--event", help="Event slug from our database")
    parser.add_argument("--url", help="Direct registration URL")
    parser.add_argument("--profile", help="Path to profile JSON file")
    parser.add_argument("--headless", action="store_true", help="Run browser headlessly")
    parser.add_argument("--dry-run", action="store_true", help="Generate answers only, don't open browser")
    args = parser.parse_args()

    if not args.event and not args.url:
        parser.error("Provide --event <slug> or --url <registration-url>")

    profile = load_profile(args.profile)
    result = asyncio.run(register_for_event(
        slug=args.event,
        url=args.url,
        profile=profile,
        headless=args.headless,
        dry_run=args.dry_run,
    ))

    print(json.dumps({k: v for k, v in result.items() if k != "screenshot"}, indent=2))


if __name__ == "__main__":
    main()

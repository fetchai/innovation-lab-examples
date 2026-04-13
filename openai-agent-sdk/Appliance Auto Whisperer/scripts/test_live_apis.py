"""
Live connectivity test for all three APIs.
Run: python scripts/test_live_apis.py
"""

import asyncio
import base64
import io
import sys
from pathlib import Path

# Load .env before importing any app modules so all settings are populated
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Force UTF-8 so emoji in YouTube titles don't crash the Windows terminal
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Clear settings cache so the freshly-loaded env vars are picked up
import app.config.settings as _settings_mod

_settings_mod.get_settings.cache_clear()


async def _get_test_image_b64() -> str:
    """Download a small public fridge/appliance photo for the vision smoke test."""
    import httpx

    url = "https://picsum.photos/seed/appliance/200/150"
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return base64.b64encode(r.content).decode("ascii")


async def test_gemini():
    from app.config.settings import get_settings

    model = get_settings().gemini_model
    print(f"\n[1] Gemini Vision  ({model})")
    print("    Downloading test image from picsum.photos...")
    b64 = await _get_test_image_b64()
    print(f"    Image size: {len(b64)} base64 chars")

    from app.services.openai.vision_part_extractor import (
        extract_part_diagnosis,
        validate_diagnosis,
    )

    print("    Calling Gemini with context 'Whirlpool WRF535SWHZ00 refrigerator'...")
    result = await extract_part_diagnosis(b64, "Whirlpool WRF535SWHZ00 refrigerator")
    err = validate_diagnosis(result)
    print(f"    part_name    : {result['part_name']}")
    print(f"    part_number  : {result['part_number']}")
    print(f"    labor_cost   : ${result['estimated_labor_cost']:.2f}")
    print(f"    confidence   : {result['confidence']:.0%}")
    print(f"    issue_summary: {result['issue_summary']}")
    live = result["confidence"] > 0 and result["part_name"] != "Unidentified part"
    print(
        f"    STATUS       : {'LIVE' if live else 'responded (low confidence on random test image is normal)'}"
    )


async def test_youtube():
    print("\n[2] YouTube Data API v3")
    print("    Query: Whirlpool WRF535SWHZ00 evaporator fan motor replacement tutorial")
    from app.services.youtube.instructor_service import find_best_tutorial_video

    url, title, dur = await find_best_tutorial_video(
        "Whirlpool WRF535SWHZ00 evaporator fan motor replacement tutorial"
    )
    print(f"    URL      : {url}")
    print(f"    Title    : {title}")
    print(f"    Duration : {dur}s  ({dur // 60}m {dur % 60}s)")
    live = "youtube.com/watch" in url
    print(f"    STATUS   : {'LIVE' if live else 'stub (no key?)'}")


async def test_brightdata():
    print("\n[3] Bright Data Web Unlocker")
    print("    Fetching RepairClinic for part W10312696...")
    from app.services.brightdata.part_price_service import fetch_parts_deterministic

    result = await fetch_parts_deterministic(
        "Evaporator Fan Motor", "W10312696", "Whirlpool"
    )
    print(f"    price_usd    : ${result['price_usd']:.2f}")
    print(f"    purchase_url : {result['purchase_url']}")
    print(f"    stock_status : {result['stock_status']}")
    stub = "stub" in str(result["stock_status"])
    print(
        f"    STATUS   : {'stub (zone not created yet — see README)' if stub else 'LIVE'}"
    )


async def main():
    print("=" * 60)
    print("Appliance Auto Whisperer — Live API Connectivity Test")
    print("=" * 60)

    from app.config.settings import get_settings

    s = get_settings()
    print(f"\nVision provider : {s.active_vision_provider or 'NONE'}")
    print(f"Gemini key      : {'OK' if s.gemini_api_key else 'MISSING'}")
    print(f"YouTube key     : {'OK' if s.youtube_api_key else 'MISSING'}")
    print(f"Bright Data     : {'OK' if s.brightdata_proxy_url else 'MISSING'}")
    print(f"Agentverse key  : {'OK' if s.agentverse_api_key else 'MISSING'}")

    await test_gemini()
    await test_youtube()
    await test_brightdata()

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Main orchestrator for the Cerebral Valley event crawl pipeline.

Two-phase approach:
  Phase 1 — API bulk ingest:
    Call the Cerebral Valley public API directly (no browser needed).
    Paginates through all 2,700+ events and upserts them to Supabase.
    Fast: ~1-2 minutes for the full dataset.

  Phase 2 — Platform detail crawl (optional, --detail flag):
    For events that have a dedicated /e/<slug> page on cerebralvalley.ai
    (platform hackathons), crawl the page for extra fields:
    hosts, registration questions, waiver, media, etc.

Usage:
    python scripts/crawl_runner.py                  # Phase 1 only (API bulk)
    python scripts/crawl_runner.py --detail         # Phase 1 + Phase 2
    python scripts/crawl_runner.py --url <url>      # Single event detail crawl
"""

import argparse
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from config import SOURCES
from crawl_browser import fetch_all_events as fetch_browser
from crawl_devpost import fetch_all_events as fetch_devpost
from crawl_event import crawl_event
from crawl_html import fetch_all_events as fetch_html
from crawl_listing import fetch_all_events as fetch_cerebralvalley
from crawl_mlh import fetch_all_events as fetch_mlh
from db import log_crawl, upsert_event


def fetch_events_for_source(source: str) -> list[dict]:
    """Dispatch to the right crawler based on the source's crawler type."""
    cfg = SOURCES.get(source, {})
    crawler_type = cfg.get("crawler", "browser")

    if source == "cerebralvalley":
        return fetch_cerebralvalley(source="cerebralvalley")
    elif source == "devpost":
        return fetch_devpost()
    elif source == "mlh":
        return fetch_mlh()
    elif crawler_type == "html":
        return fetch_html(source)
    elif crawler_type == "browser":
        return fetch_browser(source)
    else:
        print(f"[RUNNER] Unknown crawler type '{crawler_type}' for source '{source}'")
        return []


CRAWL_DELAY = 1.5  # seconds between detail page requests


def run(
    detail: bool = False, single_url: str | None = None, source: str | None = None
) -> None:
    start_time = datetime.now()
    print(f"\n{'=' * 60}")
    print(f"  Cerebral Valley Crawler — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")

    # ── Phase 1: ingest all sources (or just the one specified) ──
    sources_to_run = [source] if source else list(SOURCES.keys())
    print(f"[ PHASE 1 ] Ingesting sources: {sources_to_run}\n")

    api_events = []
    for src in sources_to_run:
        print(f"[SOURCE] {src}")
        events = fetch_events_for_source(src)
        api_events.extend(events)

    stored = errors = 0
    for event in api_events:
        ok = upsert_event(event)
        if ok:
            stored += 1
        else:
            errors += 1

    print(f"\n[PHASE 1] Complete — stored/updated: {stored}, errors: {errors}\n")

    # ── Phase 2: platform detail crawl ───────────────────────────
    if single_url:
        print("[ PHASE 2 ] Single event detail crawl\n")
        _crawl_one(single_url)

    elif detail:
        print("[ PHASE 2 ] Platform event detail crawl\n")
        # Only platform events have /e/<slug> pages with extra detail
        platform_events = [
            e for e in api_events if e.get("event_url") and _is_platform_event(e)
        ]
        print(f"[PHASE 2] {len(platform_events)} platform events to detail-crawl\n")

        p2_stored = p2_errors = 0
        for i, ev in enumerate(platform_events, 1):
            slug = ev["slug"]
            url = ev["event_url"]
            print(f"[{i:>3}/{len(platform_events)}] {slug}")
            try:
                event_data = crawl_event("cerebralvalley", slug, url)
                if event_data:
                    ok = upsert_event(event_data)
                    log_crawl("cerebralvalley", url, "success" if ok else "error", slug)
                    if ok:
                        p2_stored += 1
                        print(
                            f"  [DB] ✓ {event_data.get('title', '?')} | {event_data.get('city', '?')}\n"
                        )
                    else:
                        p2_errors += 1
                else:
                    log_crawl("cerebralvalley", url, "skipped", slug)
                    print("  [SKIP] no data\n")
            except Exception as e:
                print(f"  [ERROR] {e}\n")
                log_crawl("cerebralvalley", url, "error", slug, str(e)[:400])
                p2_errors += 1

            if i < len(platform_events):
                time.sleep(CRAWL_DELAY)

        print(
            f"[PHASE 2] Complete — stored/updated: {p2_stored}, errors: {p2_errors}\n"
        )

    # ── Summary ────────────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    print(f"  API events processed: {len(api_events)}")
    print(f"  Phase 1 stored:       {stored}")
    print(f"  Phase 1 errors:       {errors}")
    if detail or single_url:
        print(
            f"  Phase 2 stored:       {p2_stored if detail else ('1' if single_url else '0')}"
        )
    print(f"  Elapsed:              {elapsed:.1f}s")
    print(f"{'=' * 60}\n")


def _crawl_one(url: str) -> None:
    slug = url.rstrip("/").split("/")[-1]
    print(f"  Crawling: {url}")
    try:
        event_data = crawl_event("cerebralvalley", slug, url)
        if event_data:
            ok = upsert_event(event_data)
            log_crawl("cerebralvalley", url, "success" if ok else "error", slug)
            print(f"  {'✓' if ok else '✗'} {event_data.get('title', '?')}")
        else:
            print("  [SKIP] no data extracted")
    except Exception as e:
        print(f"  [ERROR] {e}")


def _is_platform_event(ev: dict) -> bool:
    """Heuristic: platform events have slugs that don't end in a UUID fragment."""
    import re

    slug = ev.get("slug", "")
    # API-derived slugs end in -{8hexchars}; real platform slugs don't
    return not re.search(r"-[0-9a-f]{8}$", slug)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cerebral Valley crawler")
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Also crawl platform event detail pages (Phase 2)",
    )
    parser.add_argument("--url", help="Crawl a single event URL directly")
    parser.add_argument(
        "--source", help=f"Only crawl this source. Options: {list(SOURCES.keys())}"
    )
    args = parser.parse_args()
    run(detail=args.detail, single_url=args.url, source=args.source)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Main orchestrator for the hackathon crawl pipeline.

Usage:
    python scripts/crawl_runner.py
    python scripts/crawl_runner.py --source cerebralvalley
    python scripts/crawl_runner.py --url https://cerebralvalley.ai/e/some-hackathon

What it does:
1. Crawls the listing page(s) to discover event URLs
2. Crawls each event page to extract full details
3. Upserts all events to Supabase with deduplication
4. Logs every crawl result to crawl_log table
5. Prints live progress and a final summary
"""

import sys
import time
import argparse
from datetime import datetime

# Make sure scripts/ is on the path
import os
sys.path.insert(0, os.path.dirname(__file__))

from config import SOURCES, BASE_URLS
from crawl_listing import crawl_listing
from crawl_event import crawl_event
from db import upsert_event, log_crawl

# --- Rate limiting: max concurrent crawls (sequential here, add asyncio if needed) ---
CRAWL_DELAY_SECONDS = 1.5


def run(source: str | None = None, single_url: str | None = None) -> None:
    sources = {source: SOURCES[source]} if source else SOURCES

    total_found = 0
    total_stored = 0
    total_skipped = 0
    total_errors = 0

    start_time = datetime.now()
    print(f"\n{'='*60}")
    print(f"  Hackathon Crawler — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    for src_name, listing_url in sources.items():
        print(f"[SOURCE] {src_name}")
        print(f"[SOURCE] Listing URL: {listing_url}\n")

        if single_url:
            # Single event mode
            slug = single_url.rstrip("/").split("/")[-1]
            events_list = [{"slug": slug, "url": single_url}]
        else:
            events_list = crawl_listing(src_name, listing_url)

        total_found += len(events_list)
        print(f"\n[PIPELINE] Processing {len(events_list)} events...\n")

        for i, ev_info in enumerate(events_list, 1):
            slug = ev_info["slug"]
            url = ev_info["url"]
            prefix = f"[{i:>3}/{len(events_list)}]"

            print(f"{prefix} {slug}")

            try:
                event_data = crawl_event(src_name, slug, url)

                if not event_data:
                    print(f"  [SKIP] No data extracted\n")
                    log_crawl(src_name, url, "skipped", event_slug=slug)
                    total_skipped += 1
                    continue

                stored = upsert_event(event_data)

                if stored:
                    title = event_data.get("title", slug)
                    city = event_data.get("city", "?")
                    start_dt = event_data.get("start_datetime", "?")
                    print(f"  [DB] ✓ stored: {title} | {city} | {start_dt}\n")
                    log_crawl(src_name, url, "success", event_slug=slug)
                    total_stored += 1
                else:
                    print(f"  [DB] ✗ upsert failed\n")
                    log_crawl(src_name, url, "error", event_slug=slug, error_msg="upsert returned False")
                    total_errors += 1

            except Exception as e:
                err = str(e)
                print(f"  [ERROR] {err}\n")
                log_crawl(src_name, url, "error", event_slug=slug, error_msg=err[:500])
                total_errors += 1

            # Polite crawl delay
            if i < len(events_list):
                time.sleep(CRAWL_DELAY_SECONDS)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Events found:   {total_found}")
    print(f"  Stored/updated: {total_stored}")
    print(f"  Skipped:        {total_skipped}")
    print(f"  Errors:         {total_errors}")
    print(f"  Elapsed:        {elapsed:.1f}s")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hackathon crawler pipeline")
    parser.add_argument("--source", help="Crawl a specific source (e.g. cerebralvalley)")
    parser.add_argument("--url", help="Crawl a single event URL directly")
    args = parser.parse_args()

    if args.source and args.source not in SOURCES:
        print(f"Unknown source '{args.source}'. Available: {list(SOURCES.keys())}")
        sys.exit(1)

    run(source=args.source, single_url=args.url)


if __name__ == "__main__":
    main()

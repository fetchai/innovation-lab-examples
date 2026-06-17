#!/usr/bin/env python3
"""
Deep crawl runner — fetches the external event page for every event that has
an external_url but no external_data yet.

Resumable: skips any event where external_data IS NOT NULL. Safe to kill and
restart at any time — progress is committed to Supabase after each event.

Estimated time: ~3s per event × 2,708 events ≈ 2.5 hours total.
Run with --source to target a specific platform first (e.g. luma).

Usage:
    python scripts/crawl_deep.py                        # all platforms
    python scripts/crawl_deep.py --source luma          # luma only
    python scripts/crawl_deep.py --source eventbrite    # eventbrite only
    python scripts/crawl_deep.py --delay 2              # custom delay (seconds)
    python scripts/crawl_deep.py --limit 50             # stop after 50 events
"""

import sys
import os
import time
import argparse
import signal
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from crawl_external import crawl_external
from db import fetch_uncrawled_events, count_uncrawled_events, update_external_data, log_crawl

# Per-platform crawl delay overrides (seconds). Some platforms are stricter.
PLATFORM_DELAYS: dict[str, float] = {
    "luma":        2.5,
    "eventbrite":  3.0,
    "meetup":      3.0,
    "partiful":    2.0,
    "devpost":     2.5,
    "lablab":      2.0,
    "external":    2.0,
}
DEFAULT_DELAY = 2.5
BATCH_SIZE = 50  # fetch this many rows from DB at a time

_stop_requested = False


def _handle_sigint(sig, frame):
    global _stop_requested
    print("\n\n[STOP] Interrupt received — finishing current event then stopping gracefully...")
    _stop_requested = True


def run(
    source_filter: str | None = None,
    delay: float | None = None,
    limit: int | None = None,
) -> None:
    global _stop_requested
    _stop_requested = False
    signal.signal(signal.SIGINT, _handle_sigint)

    total_remaining = count_uncrawled_events(source_filter)
    cap = min(limit, total_remaining) if limit else total_remaining

    start_time = datetime.now()
    print(f"\n{'='*62}")
    print(f"  Deep Crawl — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target:    {source_filter or 'all platforms'}")
    print(f"  Remaining: {total_remaining:,} events to crawl")
    if limit:
        print(f"  Limit:     {limit}")
    print(f"{'='*62}\n")

    processed = 0
    succeeded = 0
    failed = 0
    skipped = 0
    offset = 0

    while not _stop_requested:
        batch = fetch_uncrawled_events(
            batch_size=BATCH_SIZE,
            offset=0,          # always offset=0: completed rows drop out of result
            source_filter=source_filter,
        )
        if not batch:
            break

        for ev in batch:
            if _stop_requested:
                break
            if limit and processed >= limit:
                _stop_requested = True
                break

            slug = ev["slug"]
            external_url = ev.get("external_url", "")
            ext_source = ev.get("external_source") or "external"
            title = ev.get("title", slug)[:55]

            crawl_delay = delay if delay is not None else PLATFORM_DELAYS.get(ext_source, DEFAULT_DELAY)

            processed += 1
            done = processed
            pct = (done / cap * 100) if cap else 0
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = done / elapsed if elapsed > 0 else 0
            eta_s = ((cap - done) / rate) if rate > 0 else 0
            eta_str = str(timedelta(seconds=int(eta_s))) if eta_s else "?"

            print(
                f"[{done:>4}/{cap}] ({pct:4.1f}%) ETA {eta_str} | "
                f"{ext_source:12s} | {title}"
            )

            if not external_url:
                print(f"  [SKIP] no external_url")
                update_external_data(slug, {"_skipped": True, "_reason": "no_url"})
                skipped += 1
                continue

            try:
                data = crawl_external(external_url, ext_source)
                ok = update_external_data(slug, data, error=bool(data.get("error")))
                log_crawl(ext_source, external_url, "success" if ok else "error", slug)
                if ok:
                    succeeded += 1
                else:
                    failed += 1
            except Exception as e:
                err_str = str(e)[:400]
                print(f"  [ERROR] {err_str}")
                update_external_data(slug, {"error": err_str, "_source": ext_source})
                log_crawl(ext_source, external_url, "error", slug, err_str)
                failed += 1

            time.sleep(crawl_delay)

        # If we got fewer than BATCH_SIZE, we're done
        if len(batch) < BATCH_SIZE:
            break

    elapsed_total = (datetime.now() - start_time).total_seconds()
    remaining_after = count_uncrawled_events(source_filter)

    print(f"\n{'='*62}")
    print(f"  DEEP CRAWL SUMMARY")
    print(f"{'='*62}")
    print(f"  Processed:  {processed:,}")
    print(f"  Succeeded:  {succeeded:,}")
    print(f"  Failed:     {failed:,}")
    print(f"  Skipped:    {skipped:,}")
    print(f"  Remaining:  {remaining_after:,}")
    print(f"  Elapsed:    {str(timedelta(seconds=int(elapsed_total)))}")
    print(f"{'='*62}\n")

    if remaining_after > 0 and not (limit and processed >= limit):
        print(f"  Resume with: python scripts/crawl_deep.py"
              + (f" --source {source_filter}" if source_filter else ""))
    elif remaining_after == 0:
        print("  All events fully crawled!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep crawl external event pages")
    parser.add_argument("--source", help="Only crawl events from this platform (e.g. luma, eventbrite)")
    parser.add_argument("--delay", type=float, help="Override crawl delay in seconds")
    parser.add_argument("--limit", type=int, help="Stop after this many events")
    args = parser.parse_args()
    run(source_filter=args.source, delay=args.delay, limit=args.limit)


if __name__ == "__main__":
    main()

"""
Aggregator Agent — port 8013

Sits between the per-video location extractors and the trip planner. When the
user pastes 1-4 YouTube URLs in one chat message, the orchestrator fans out
transcript + location extraction in parallel, then ships every per-video
location list here.

What this agent does:
  1. Normalise + dedupe location names across all videos (case-insensitive,
     whitespace + parenthetical trim, simple substring merge).
  2. Count cross-video frequency for each unique location.
  3. Call Google Places once per unique name to validate it AND grab the
     rating + place_id + lat/lng + formatted address.
  4. Score every validated stop:
        score = (frequency / max_frequency) * 60   # consensus weight 60%
              + (rating / 5.0)            * 40    # quality   weight 40%
  5. Return the ranked list (highest score first), already shaped for the
     trip planner — no separate geocoder call needed downstream.

Notes:
  • Single-URL flows still work: max_frequency = 1, every stop has frequency
    = 1, so the score collapses to a pure rating ranking.
  • Places lookups run in a thread pool so a 100-unique-location batch takes
    ~5s instead of ~50s.
"""

import os
import re
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
import googlemaps
from uagents import Agent, Context

from shared_models import AggregateRequest, AggregateResponse

load_dotenv()

agent = Agent(
    name="aggregator_agent",
    seed=os.getenv("AGGREGATOR_SEED"),
    port=8013,
    endpoint=[os.getenv("AGGREGATOR_ENDPOINT", "http://localhost:8013/submit")],
    network="testnet",
)

gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

# How many ranked stops to return to the planner. Anything past ~25 is
# wasted tokens — the planner only ever uses 6-12 in a real itinerary.
_MAX_RANKED_STOPS = 25
# Drop anything with a Places rating below this floor, even if it appeared
# in multiple videos. Catches gas stations / random businesses that match
# textually but aren't real destinations.
_MIN_RATING_FLOOR = 3.0


# ── Normalisation / dedupe ───────────────────────────────────────────────────

_PARENS_RE = re.compile(r"\s*\([^)]*\)\s*")
_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def _normalise(name: str) -> str:
    """Aggressive normalisation just for grouping equivalent mentions.

    e.g. "Yosemite Valley", "yosemite valley.", "Yosemite Valley (CA)"
    all collapse to "yosemite valley".
    """
    s = name.lower().strip()
    s = _PARENS_RE.sub(" ", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def _build_groups(videos: list) -> dict:
    """Group raw mentions by normalised name across all videos.

    Returns:
      { normalised_name: {
            "display_name": str,            # most-popular original casing
            "video_indices": set[int],      # which videos mentioned it
        }, ... }
    """
    groups: dict = {}
    for v in videos:
        v_idx = int(v.get("video_index", 0))
        for raw in v.get("locations", []) or []:
            raw = (raw or "").strip()
            if not raw:
                continue
            key = _normalise(raw)
            if not key:
                continue
            entry = groups.setdefault(
                key,
                {
                    "display_candidates": {},  # { original_text: count }
                    "video_indices": set(),
                },
            )
            entry["display_candidates"][raw] = (
                entry["display_candidates"].get(raw, 0) + 1
            )
            entry["video_indices"].add(v_idx)

    # Pick the most popular original-casing variant as the display name.
    final = {}
    for key, entry in groups.items():
        candidates = entry["display_candidates"]
        display = max(candidates.items(), key=lambda kv: kv[1])[0]
        final[key] = {
            "display_name": display,
            "video_indices": sorted(entry["video_indices"]),
        }
    return final


# ── Places lookup ────────────────────────────────────────────────────────────


def _lookup_place(name: str) -> dict | None:
    """Return a validated Place dict for *name*, or None if not found."""
    try:
        result = gmaps.places(query=name)
        if result.get("status") != "OK" or not result.get("results"):
            return None
        place = result["results"][0]
        photos = place.get("photos") or []
        photo_ref = photos[0].get("photo_reference", "") if photos else ""
        return {
            "name": place.get("name", name),
            "address": place.get("formatted_address", ""),
            "lat": place["geometry"]["location"]["lat"],
            "lng": place["geometry"]["location"]["lng"],
            "place_id": place.get("place_id", ""),
            "rating": float(place.get("rating", 0.0) or 0.0),
            "photo_reference": photo_ref,
        }
    except Exception:
        return None


def _maps_url_for(stops: list) -> str:
    """Build a quick Google Maps driving URL for the top stops.

    Used only as a fallback — the orchestrator usually rebuilds a cleaner
    URL from the trip planner's day-by-day output.
    """
    if not stops:
        return ""
    if len(stops) == 1:
        only = stops[0]
        return (
            f"https://www.google.com/maps/search/?api=1"
            f"&query={quote(only['name'])}"
            f"&query_place_id={only['place_id']}"
        )
    origin = quote(stops[0]["address"])
    destination = quote(stops[-1]["address"])
    waypoints = "|".join(quote(p["address"]) for p in stops[1:-1][:9])
    url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={origin}"
        f"&destination={destination}"
        f"&travelmode=driving"
    )
    if waypoints:
        url += f"&waypoints={waypoints}"
    return url


# ── Scoring ──────────────────────────────────────────────────────────────────


def _score(frequency: int, rating: float, max_freq: int) -> float:
    """60% consensus, 40% rating. Range: 0-100."""
    if max_freq <= 0:
        max_freq = 1
    freq_score = (frequency / max_freq) * 60.0
    rating_score = (max(rating, 0.0) / 5.0) * 40.0
    return round(freq_score + rating_score, 2)


# ── Handler ──────────────────────────────────────────────────────────────────


@agent.on_message(AggregateRequest)
async def handle_aggregate(ctx: Context, sender: str, msg: AggregateRequest):
    videos = msg.videos or []
    total_raw = sum(len(v.get("locations") or []) for v in videos)
    ctx.logger.info(f"Aggregating {total_raw} raw mentions from {len(videos)} video(s)")

    if not videos:
        await ctx.send(
            sender,
            AggregateResponse(
                success=False,
                error="No videos provided to aggregator.",
            ),
        )
        return

    groups = _build_groups(videos)
    ctx.logger.info(f"Deduped to {len(groups)} unique location names")

    if not groups:
        await ctx.send(
            sender,
            AggregateResponse(
                success=False,
                error="No location names found across the supplied videos.",
            ),
        )
        return

    # Look up Google Places for every unique name — in parallel.
    keys = list(groups.keys())
    display_names = [groups[k]["display_name"] for k in keys]

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            place_results = list(pool.map(_lookup_place, display_names))
    except Exception as e:
        ctx.logger.error(f"Aggregator Places lookup failed: {e}")
        await ctx.send(
            sender,
            AggregateResponse(
                success=False,
                error=f"Google Places error: {e}",
            ),
        )
        return

    # Compute max frequency for normalisation BEFORE filtering — we want
    # consistent scoring across the whole batch.
    max_freq = max((len(groups[k]["video_indices"]) for k in keys), default=1)

    ranked: list = []
    skipped = 0
    for key, place in zip(keys, place_results):
        meta = groups[key]
        if place is None:
            skipped += 1
            ctx.logger.info(f"Could not validate: {meta['display_name']}")
            continue
        # Filter out obviously non-touristy matches by rating floor, but
        # only when frequency = 1. Multi-video consensus can override.
        freq = len(meta["video_indices"])
        if freq <= 1 and place["rating"] < _MIN_RATING_FLOOR:
            skipped += 1
            continue

        ranked.append(
            {
                **place,
                "frequency": freq,
                "mentioned_in_videos": meta["video_indices"],
                "score": _score(freq, place["rating"], max_freq),
            }
        )

    ranked.sort(key=lambda s: s["score"], reverse=True)
    ranked = ranked[:_MAX_RANKED_STOPS]

    if not ranked:
        await ctx.send(
            sender,
            AggregateResponse(
                success=False,
                error=(
                    "All candidate locations failed validation in Google Places "
                    "or fell below the rating floor."
                ),
            ),
        )
        return

    maps_url = _maps_url_for(ranked[:9])  # Maps caps waypoints at ~9
    consensus = sum(1 for s in ranked if s["frequency"] >= 2)
    ctx.logger.info(
        f"Ranked {len(ranked)} stop(s); {consensus} appeared in >=2 videos. "
        f"Top: {ranked[0]['name']} (score {ranked[0]['score']})"
    )

    await ctx.send(
        sender,
        AggregateResponse(
            success=True,
            ranked_stops=ranked,
            total_unique_locations=len(groups),
            total_raw_mentions=total_raw,
            skipped_count=skipped,
            maps_url=maps_url,
        ),
    )


if __name__ == "__main__":
    agent.run()

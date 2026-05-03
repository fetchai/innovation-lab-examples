"""
Trip Planner Agent — port 8011

Sits between the geocoder and the PDF generator in the video-to-map pipeline.
Takes the full validated-stops list from the geocoder plus the user's budget,
trip length, and preferences, and produces a curated day-by-day itinerary.

What it actually does:
  1. Asks ASI1 to filter logistical noise, cluster by proximity, and assign
     each kept stop to a day with a short activity, duration, and cost.
  2. For each stop it enriches the plan with a Google Places nearby-search
     for restaurants matching the user's dietary preferences (vegetarian by
     default). Restaurant lookups run in a thread pool to keep latency low.

The output is a TripPlannerResponse with a `days` array shaped so the PDF
generator can render it page-by-page without any additional shaping.
"""

import os
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from openai import OpenAI
import googlemaps
from uagents import Agent, Context

from shared_models import TripPlannerRequest, TripPlannerResponse

load_dotenv()

agent = Agent(
    name="trip_planner_agent",
    seed=os.getenv("TRIP_PLANNER_SEED"),
    port=8011,
    endpoint=[os.getenv("TRIP_PLANNER_ENDPOINT", "http://localhost:8011/submit")],
    network="testnet",
)

asi1_client = OpenAI(
    base_url="https://api.asi1.ai/v1",
    api_key=os.getenv("ASI1_API_KEY"),
)

gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

# How many stops to keep per day on the high end. ASI1 is asked to be
# realistic but we hard-clamp here so a bad LLM response can't produce a
# 15-stop day.
_MAX_STOPS_PER_DAY = 4
# Nearby-restaurant search radius (metres).
_RESTAURANT_RADIUS_M = 5000
# Max restaurants kept per stop.
_RESTAURANTS_PER_STOP = 3


def _detect_dietary_keyword(preferences: str) -> str:
    """Return a short dietary keyword to pass to Google Places nearby-search.

    We look for common flags in the free-form preferences string the user
    wrote in chat. If nothing matches we just return "" so the search falls
    back to generic restaurants.
    """
    if not preferences:
        return ""
    p = preferences.lower()
    for kw in ("vegan", "vegetarian", "halal", "kosher", "gluten-free", "pescatarian"):
        if kw in p:
            return kw
    return ""


def _find_nearby_restaurants(stop: dict, dietary_keyword: str) -> list:
    """Return up to _RESTAURANTS_PER_STOP nearby restaurants for *stop*.

    Safe to run in a thread pool — both the Google Maps client and JSON
    parsing are thread-safe.
    """
    try:
        kwargs = dict(
            location=(stop["lat"], stop["lng"]),
            radius=_RESTAURANT_RADIUS_M,
            type="restaurant",
        )
        if dietary_keyword:
            kwargs["keyword"] = dietary_keyword
        result = gmaps.places_nearby(**kwargs)
        places = result.get("results", [])[:_RESTAURANTS_PER_STOP]
        return [
            {
                "name": p.get("name", ""),
                "address": p.get("vicinity", ""),
                "rating": float(p.get("rating", 0.0) or 0.0),
            }
            for p in places
        ]
    except Exception:
        return []


def _resolve_budget_and_days(
    budget_per_day: float,
    total_budget: float,
    trip_days: int,
) -> tuple[float, int, str]:
    """Reconcile the three budget/day inputs into concrete numbers.

    Returns: (effective_budget_per_day, effective_trip_days, source_label)
    where source_label explains the reasoning so the orchestrator can
    surface it to the user.

    Rules:
      • per_day + days  → use both as-is.
      • only total      → days = round(total / 80) (clamped to [1,7]).
                          per_day = total / days.
      • only per_day    → days defaults to 3.
      • neither         → defaults of $100/day, 3 days.
      • only days, no $ → defaults to $100/day for that day count.
    """
    have_per_day = budget_per_day and budget_per_day > 0
    have_total = total_budget and total_budget > 0
    have_days = trip_days and trip_days > 0

    if have_per_day and have_days:
        return (
            budget_per_day,
            trip_days,
            (f"using your ${budget_per_day:.0f}/day x {trip_days} days"),
        )

    if have_total and not have_days:
        # Estimated daily cost floor used for day derivation. Keep this
        # conservative — better to plan one extra day than overbook.
        est_daily = 80.0
        days = max(1, min(7, round(total_budget / est_daily)))
        per_day = total_budget / days
        return (
            per_day,
            days,
            (
                f"derived {days} day(s) from ${total_budget:.0f} total "
                f"(~${per_day:.0f}/day)"
            ),
        )

    if have_total and have_days:
        per_day = total_budget / trip_days
        return (
            per_day,
            trip_days,
            (
                f"using ${total_budget:.0f} total over {trip_days} days "
                f"(~${per_day:.0f}/day)"
            ),
        )

    if have_per_day:
        return (
            budget_per_day,
            3,
            (f"using ${budget_per_day:.0f}/day, defaulting to 3 days"),
        )

    if have_days:
        return 100.0, trip_days, (f"using {trip_days} days at default $100/day")

    return 100.0, 3, "using defaults (3 days at $100/day)"


def _curate_with_asi1(
    validated_stops: list,
    budget_per_day: float,
    trip_days: int,
    preferences: str,
) -> dict:
    """Call ASI1 to produce a day-by-day plan from the ranked validated stops.

    `validated_stops` may carry extra scoring metadata from the aggregator
    (frequency, rating, score, mentioned_in_videos). We pass that to ASI1
    so it can prefer consensus stops over single-mention ones.
    """
    # Carry scoring metadata into the prompt when present so ASI1 can
    # prefer consensus stops. We keep the JSON small.
    stops_for_prompt = []
    for s in validated_stops:
        entry = {
            "name": s["name"],
            "address": s.get("address", ""),
            "lat": s["lat"],
            "lng": s["lng"],
        }
        # These fields only exist when the aggregator was used.
        if "frequency" in s:
            entry["videos_mentioned"] = int(s.get("frequency", 1))
        if "rating" in s and s.get("rating"):
            entry["google_rating"] = float(s["rating"])
        if "score" in s:
            entry["consensus_score"] = float(s["score"])
        stops_for_prompt.append(entry)

    has_scores = any("consensus_score" in s for s in stops_for_prompt)
    scoring_note = (
        "\nThe candidate stops include three signals you should use:\n"
        "  - videos_mentioned: how many of the user's source videos "
        "called out this place. Higher = stronger crowd consensus.\n"
        "  - google_rating: Google Places average rating (0-5).\n"
        "  - consensus_score: precomputed 0-100 blend of the above. "
        "Higher is better. Strongly prefer high-score stops.\n"
        if has_scores
        else ""
    )

    user_prompt = (
        f"You are curating a realistic {trip_days}-day road trip with a "
        f"budget of ${budget_per_day:.0f} per person per day.\n"
        f"Traveler preferences: {preferences or 'no specific preferences'}.\n"
        f"{scoring_note}\n"
        "Here is the candidate list. Many will be logistical noise — gas "
        "stations, highway strips, random towns, or duplicates. Your job:\n"
        "1. Drop anything that isn't a true destination-worth-stopping-for.\n"
        "2. Drop duplicates and near-duplicates.\n"
        "3. Cluster the remaining stops by proximity to MINIMISE drive "
        "time. The order stops appeared in the source videos is "
        "irrelevant — sequence by geography.\n"
        f"4. Select the best stops that realistically fit into {trip_days} "
        f"days. At most {_MAX_STOPS_PER_DAY} stops per day. When choosing "
        "between stops, prefer high consensus_score and the traveler's "
        "preferences.\n"
        "5. Assign each kept stop to a specific day (1-indexed) in driving "
        "order so each day flows logically without backtracking.\n"
        "6. For each stop, write a short (<= 8 words) activity description "
        "and estimate duration in hours (integer).\n"
        "7. For each day, write a short theme (<= 5 words) and estimate a "
        "per-person cost in USD that respects the daily budget.\n\n"
        "Return ONLY valid JSON of this exact shape (no prose, no markdown):\n"
        "{\n"
        '  "days": [\n'
        "    {\n"
        '      "day_number": 1,\n'
        '      "theme": "Arrival + Lake Area",\n'
        '      "estimated_cost_usd": 95.0,\n'
        '      "stops": [\n'
        "        {\n"
        '          "name": "Lake Siskiyou",\n'
        '          "activity": "kayaking and lakeside picnic",\n'
        '          "duration_hours": 3\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ],\n"
        '  "reasoning": "one-sentence summary of the curation you just did"\n'
        "}\n\n"
        f"Candidate stops:\n{json.dumps(stops_for_prompt)}"
    )

    resp = asi1_client.chat.completions.create(
        model="asi1-mini",
        max_tokens=2000,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert road-trip planner. "
                    "You ALWAYS return valid JSON that matches the schema "
                    "the user asks for. No markdown, no commentary."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def _merge_plan_with_geocoded(
    plan: dict,
    validated_stops: list,
) -> list:
    """Hydrate the ASI1 plan with the full geocoded stop info.

    ASI1 only sees name/address/lat/lng. To produce a PDF-ready structure
    we need to carry `place_id` and the full formatted address back through.
    Matching is done by case-insensitive name + proximity fallback.
    """
    by_name = {s["name"].lower(): s for s in validated_stops}

    hydrated_days: list[dict] = []
    for day in plan.get("days", []):
        day_stops_in = day.get("stops", [])
        day_stops_out = []
        for s in day_stops_in[:_MAX_STOPS_PER_DAY]:
            src = by_name.get((s.get("name") or "").lower())
            if src is None:
                # ASI1 may have slightly renamed — fall back to nearest-by-
                # name substring match. Skip if we can't find one.
                candidate = next(
                    (
                        v
                        for v in validated_stops
                        if v["name"].lower() in (s.get("name") or "").lower()
                        or (s.get("name") or "").lower() in v["name"].lower()
                    ),
                    None,
                )
                if candidate is None:
                    continue
                src = candidate

            day_stops_out.append(
                {
                    "name": src["name"],
                    "address": src.get("address", ""),
                    "lat": src["lat"],
                    "lng": src["lng"],
                    "place_id": src.get("place_id", ""),
                    "activity": s.get("activity", "") or "",
                    "duration_hours": int(s.get("duration_hours", 2) or 2),
                    "nearby_restaurants": [],
                    "frequency": int(src.get("frequency", 1) or 1),
                    "rating": float(src.get("rating", 0.0) or 0.0),
                    "score": float(src.get("score", 0.0) or 0.0),
                    "mentioned_in_videos": list(
                        src.get("mentioned_in_videos", []) or []
                    ),
                    "photo_reference": src.get("photo_reference", ""),
                }
            )

        if not day_stops_out:
            continue

        hydrated_days.append(
            {
                "day_number": int(day.get("day_number", len(hydrated_days) + 1)),
                "theme": (day.get("theme") or "").strip() or "Road Trip Day",
                "estimated_cost_usd": float(day.get("estimated_cost_usd", 0.0) or 0.0),
                "stops": day_stops_out,
            }
        )

    return hydrated_days


def _enrich_with_restaurants(hydrated_days: list, dietary_keyword: str) -> None:
    """In-place: populate `nearby_restaurants` on every stop concurrently."""
    # Collect every stop across all days into a flat list so one pool can
    # saturate all requests in parallel.
    all_stops = [stop for day in hydrated_days for stop in day["stops"]]
    if not all_stops:
        return

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda stop: _find_nearby_restaurants(stop, dietary_keyword),
                all_stops,
            )
        )

    for stop, restaurants in zip(all_stops, results):
        stop["nearby_restaurants"] = restaurants


def _assess_budget(
    total_cost: float, total_budget: float, budget_per_day: float, days: int
) -> str:
    """Return one of: 'fits' | 'tight' | 'over' | '' (no budget given)."""
    target = (
        total_budget
        if total_budget and total_budget > 0
        else (budget_per_day * days if budget_per_day > 0 else 0)
    )
    if target <= 0:
        return ""
    if total_cost <= target:
        return "fits"
    if total_cost <= target * 1.10:
        return "tight"
    return "over"


@agent.on_message(TripPlannerRequest)
async def handle_trip_planner(ctx: Context, sender: str, msg: TripPlannerRequest):
    eff_per_day, eff_days, source_label = _resolve_budget_and_days(
        msg.budget_per_day,
        msg.total_budget,
        msg.trip_days,
    )
    ctx.logger.info(
        f"Planning trip: {len(msg.validated_stops)} candidate stops, "
        f"{eff_days} day(s), ${eff_per_day:.0f}/day "
        f"({source_label}); preferences={msg.preferences!r}"
    )

    if not msg.validated_stops:
        await ctx.send(
            sender,
            TripPlannerResponse(
                success=False,
                error="No validated stops were provided to the trip planner.",
            ),
        )
        return

    try:
        plan = _curate_with_asi1(
            msg.validated_stops,
            eff_per_day,
            eff_days,
            msg.preferences,
        )
    except Exception as e:
        ctx.logger.error(f"ASI1 curation failed: {e}")
        await ctx.send(
            sender,
            TripPlannerResponse(
                success=False,
                error=f"ASI1 curation failed: {e}",
            ),
        )
        return

    hydrated_days = _merge_plan_with_geocoded(plan, msg.validated_stops)
    if not hydrated_days:
        await ctx.send(
            sender,
            TripPlannerResponse(
                success=False,
                error="ASI1 returned a plan with no recognisable stops.",
            ),
        )
        return

    dietary_keyword = _detect_dietary_keyword(msg.preferences)
    ctx.logger.info(
        f"Curated to {sum(len(d['stops']) for d in hydrated_days)} stops "
        f"across {len(hydrated_days)} day(s). Looking up "
        f"{dietary_keyword or 'generic'} restaurants near each stop..."
    )

    _enrich_with_restaurants(hydrated_days, dietary_keyword)

    total_cost = sum(d["estimated_cost_usd"] for d in hydrated_days)
    reasoning = (plan.get("reasoning") or "").strip()
    if source_label:
        reasoning = (
            f"{reasoning} Budget plan: {source_label}."
            if reasoning
            else f"Budget plan: {source_label}."
        )

    actual_days = len(hydrated_days)
    assessment = _assess_budget(
        total_cost,
        msg.total_budget,
        eff_per_day,
        actual_days,
    )

    ctx.logger.info(
        f"Plan ready: {actual_days} day(s), total est. ${total_cost:.0f} "
        f"(budget assessment: {assessment or 'n/a'})."
    )
    await ctx.send(
        sender,
        TripPlannerResponse(
            success=True,
            days=hydrated_days,
            total_estimated_cost=total_cost,
            reasoning=reasoning,
            budget_assessment=assessment,
            derived_trip_days=actual_days,
        ),
    )


if __name__ == "__main__":
    agent.run()

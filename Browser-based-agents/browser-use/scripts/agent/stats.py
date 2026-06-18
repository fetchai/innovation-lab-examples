"""
Stat/aggregate queries for the "stat" intent.
Uses pre-defined supabase-py queries rather than raw SQL to avoid
dependency on a custom execute_sql RPC function.
ASI:One classifies the stat type and narrates the result.
"""

import re
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL, ASI_ONE_MODEL
from db import get_client
from datetime import datetime, timezone

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def answer_stat(stat_query: str) -> str:
    """Classify the stat type, run the right query, narrate the answer."""
    stat_type = _classify_stat(stat_query)
    rows = _run_stat(stat_type, stat_query)
    return _narrate(stat_query, rows)


def _classify_stat(query: str) -> str:
    """Return one of: by_platform, by_location, upcoming_count, prize, online, general."""
    q = query.lower()
    if any(w in q for w in ["platform", "source", "site", "website"]):
        return "by_platform"
    if any(w in q for w in ["location", "city", "country", "where"]):
        return "by_location"
    if any(w in q for w in ["prize", "money", "cash", "award"]):
        return "prize"
    if any(w in q for w in ["online", "virtual", "remote", "digital"]):
        return "online"
    if any(w in q for w in ["upcoming", "next", "future", "soon"]):
        return "upcoming_count"
    return "general"


def _run_stat(stat_type: str, query: str) -> list[dict]:
    """Execute the appropriate supabase-py query."""
    client = get_client()

    try:
        if stat_type == "by_platform":
            # Count events per source platform
            rows = client.table("events").select("source").gte("start_datetime", TODAY).execute().data or []
            from collections import Counter
            counts = Counter(r["source"] for r in rows)
            return [{"platform": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]

        elif stat_type == "by_location":
            rows = client.table("events").select("city").not_.is_("city", "null").gte("start_datetime", TODAY).limit(1000).execute().data or []
            from collections import Counter
            cities = Counter(r["city"] for r in rows if r.get("city"))
            return [{"city": k, "count": v} for k, v in sorted(cities.items(), key=lambda x: -x[1])[:15]]

        elif stat_type == "prize":
            # Events that have prize info
            rows = client.table("events") \
                .select("title, source, start_datetime, llm_extracted") \
                .not_.is_("llm_extracted", "null") \
                .gte("start_datetime", TODAY) \
                .limit(500).execute().data or []

            prizes = []
            for r in rows:
                le = r.get("llm_extracted") or {}
                if isinstance(le, str):
                    try:
                        le = json.loads(le)
                    except Exception:
                        continue
                prize = le.get("prize_amount")
                if prize:
                    prizes.append({"title": r["title"], "prize": prize, "source": r["source"]})

            return prizes[:20]

        elif stat_type == "online":
            rows = client.table("events") \
                .select("source, title, city") \
                .or_("city.ilike.%worldwide%,city.ilike.%online%,city.ilike.%digital%,city.ilike.%everywhere%,city.ilike.%remote%") \
                .gte("start_datetime", TODAY) \
                .limit(200).execute().data or []
            from collections import Counter
            counts = Counter(r["source"] for r in rows)
            return [{"count": len(rows), "by_platform": dict(counts)}]

        elif stat_type == "upcoming_count":
            rows = client.table("events").select("source").gte("start_datetime", TODAY).execute().data or []
            from collections import Counter
            counts = Counter(r["source"] for r in rows)
            return [{"total_upcoming": len(rows), "by_platform": dict(counts)}]

        else:
            # General: total count by source
            rows = client.table("events").select("source").execute().data or []
            from collections import Counter
            counts = Counter(r["source"] for r in rows)
            return [{"platform": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]

    except Exception as e:
        print(f"  [STATS] query failed: {e}")
        return []


def _narrate(question: str, rows: list) -> str:
    """Use ASI:One to turn raw results into a friendly natural language answer."""
    if not rows:
        return "I couldn't find data for that query. Try rephrasing."

    rows_text = json.dumps(rows[:15], indent=2)

    prompt = f"""A user asked: "{question}"

Here is the data retrieved from our hackathon database:
{rows_text}

Write a concise, friendly answer in 2-4 sentences. Include key numbers and highlights. Don't mention technical details or JSON."""

    try:
        resp = httpx.post(
            f"{ASI_ONE_BASE_URL}/chat/completions",
            json={
                "model": ASI_ONE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 250,
                "temperature": 0.3,
            },
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}"},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return f"Results: {rows_text}"

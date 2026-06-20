"""
Parse a natural language question into a structured intent + prefs dict.

Uses ASI:One to extract:
  - intent: "search" | "lookup" | "stat" | "general"
  - prefs: dict matching recommend/filter.py expectations
  - event_name: str (for lookup intent)
  - answer: str (for general intent — answered directly without DB)
"""

import json
import re
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import httpx
from config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL, ASI_ONE_MODEL

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_question(question: str) -> dict:
    """
    Returns a dict with:
        intent      : "search" | "lookup" | "stat" | "general"
        prefs       : dict  (for search intent)
        event_name  : str   (for lookup intent)
        stat_query  : str   (for stat intent — plain English query)
        answer      : str   (for general intent — answered directly)
    """
    prompt = f"""Today's date is {TODAY}.

You are a parser for a hackathon discovery assistant. Given the user's question, extract structured information.

Return ONLY a JSON object (no markdown). Choose one intent:

1. "search" — user wants recommendations/list of events
   Extract prefs:
     keywords    : str — ONLY specific tech/topic terms (e.g. "AI", "Web3", "LLM", "robotics").
                   NEVER put generic words like "hackathon", "hackathons", "event", "events",
                   "find", "show", "upcoming", "next", "looking for" into keywords.
                   Leave empty string "" if the user just wants hackathons with no specific topic.
     topics      : list of tech topics extracted from the query
     location    : str city/country, or null if not specified
     online      : bool — true only if user explicitly wants online/virtual/remote events
     date_from   : YYYY-MM-DD or null
     date_to     : YYYY-MM-DD or null
     hackathon_only : bool — true whenever user says "hackathon(s)" or is clearly looking for hackathons
     registration_open : bool — true if user wants open/joinable events
     min_prize   : int USD or null
     team_size   : str or null
     sources     : list of platform names or null

2. "lookup" — user asks about a specific named event
   Extract event_name (str)

3. "stat" — user wants a count or aggregate ("how many", "which platforms", "average prize")
   Extract stat_query (plain English description of what to count/aggregate)

4. "general" — general knowledge question not needing DB lookup
   Provide a short direct answer field.

Examples:
- "find hackathons in SF" → search, keywords="", location="San Francisco", hackathon_only=true
- "find AI hackathons in SF next month" → search, keywords="AI", location="San Francisco", hackathon_only=true
- "upcoming web3 events" → search, keywords="Web3", hackathon_only=false
- "tell me about the AIEWF hackathon" → lookup
- "how many online hackathons have prizes over $10k?" → stat
- "what is a hackathon?" → general

User question: {question}

Return JSON:
{{
  "intent": "search|lookup|stat|general",
  "prefs": {{ ... }},        // only for search
  "event_name": "...",      // only for lookup
  "stat_query": "...",      // only for stat
  "answer": "..."           // only for general
}}"""

    try:
        resp = httpx.post(
            f"{ASI_ONE_BASE_URL}/chat/completions",
            json={
                "model": ASI_ONE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0,
            },
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        print(f"  [PARSE] failed: {e} — defaulting to search")
        return {
            "intent": "search",
            "prefs": {"keywords": question},
        }

"""
Personalized coaching layer.

Takes the deterministic TestResult plus the user's age and turns it into a
short, conversational coach paragraph using ASI:One. The structured numbers
are still shown first — the coach paragraph is added below for color and
context.

Falls back to a static encouraging message if ASI:One is unreachable.
"""

from __future__ import annotations

import os

from openai import OpenAI

from history import TestRecord, time_since
from scoring import TestResult

ASI1_BASE_URL = "https://api.asi1.ai/v1"


SYSTEM_PROMPT = """You are a careful, honest cardiovascular health coach.

You will be given:
- A user's age
- Their measured Cardio Fitness Age estimate from today's test
- Resting HR, orthostatic delta (HR jump on standing), and breathing-driven
  HR variance from today's 3-minute test
- The user-facing grade for resting HR
- Optionally, the same metrics from their previous test plus when it was taken

Your job: write a 3-5 sentence coach paragraph.

Rules:
- If a DATA QUALITY WARNING is present, lead with THAT: tell the user plainly
  that this reading is low-confidence and why, and do not draw strong
  conclusions or alarming comparisons from it. Suggest how to get a clean
  reading instead.
- Otherwise, if a previous test is provided, lead with the trend: did the
  score improve, stay flat, or worsen, and by how much. Make the trend the
  most prominent part of the message — it's what makes the coaching feel
  personalised. If the trend and an individual metric disagree, say which
  one the user should trust and why, in one sentence — never present a
  contradiction without resolving it.
- If no previous test is provided, lead with today's result, acknowledged
  honestly. If the score is alarming, name the most likely benign cause
  (caffeine, stress, recent activity, NOT a true rested state) before
  suggesting anything.
- Reference at least one specific number so the user knows you read the data.
- Suggest ONE concrete action they can take in the next 24 hours (not a list).
- Be encouraging but not patronising. No emojis. No motivational fluff.
- Never claim clinical diagnosis. Use "may", "could suggest", "likely".
- Total length: 3-5 sentences. No headings, no bullet lists.
"""


def _build_prompt(result: TestResult, previous: TestRecord | None = None) -> str:
    lines = [
        "TODAY'S TEST:",
        f"  Chronological age: {result.age}",
        f"  Cardio Fitness Age: {result.cardio_fitness_age}",
        f"  Verdict: {result.verdict}",
        f"  Resting HR: {result.resting_hr} bpm (grade: {result.rhr_grade})",
        f"  Orthostatic HR delta: +{result.orthostatic_delta} bpm",
        f"  Breathing-driven HR variance: {result.breathing_variance} bpm",
    ]

    if result.quality_note:
        lines.append(f"  DATA QUALITY WARNING: {result.quality_note}")

    if previous is not None:
        cardio_delta = result.cardio_fitness_age - previous.cardio_fitness_age
        rhr_delta = result.resting_hr - previous.resting_hr
        when = time_since(previous)

        if cardio_delta < 0:
            direction = f"improved by {abs(cardio_delta)} year(s)"
        elif cardio_delta > 0:
            direction = f"worsened by {cardio_delta} year(s)"
        else:
            direction = "stayed the same"

        lines.extend(
            [
                "",
                f"PREVIOUS TEST ({when}):",
                f"  Cardio Fitness Age: {previous.cardio_fitness_age}",
                f"  Resting HR: {previous.resting_hr} bpm",
                f"  Orthostatic HR delta: +{previous.orthostatic_delta} bpm",
                "",
                "TREND:",
                f"  Cardio Fitness Age has {direction} since the previous test.",
                f"  Resting HR is {'down' if rhr_delta < 0 else 'up' if rhr_delta > 0 else 'flat'} "
                f"{abs(rhr_delta)} bpm.",
            ]
        )

    return "\n".join(lines)


def _fallback(result: TestResult, previous: TestRecord | None = None) -> str:
    """Static encouraging message when ASI:One is unavailable."""
    if previous is not None:
        cardio_delta = result.cardio_fitness_age - previous.cardio_fitness_age
        when = time_since(previous)
        if cardio_delta < 0:
            return (
                f"Your Cardio Fitness Age improved by {abs(cardio_delta)} year(s) "
                f"since your previous test ({when}). Keep doing whatever you've been "
                "doing — the trend is what matters."
            )
        elif cardio_delta > 0:
            return (
                f"Your Cardio Fitness Age is {cardio_delta} year(s) higher than your "
                f"previous test ({when}). Could be a less-rested baseline today — "
                "try re-testing in the same conditions to confirm the trend."
            )
        else:
            return (
                f"Your Cardio Fitness Age is the same as your previous test ({when}). "
                "Steady is a good sign. The needle moves slowly — keep at it."
            )

    if result.cardio_fitness_age <= result.age:
        return (
            "Your cardiovascular function is reading at or below your age. "
            "Keep doing what you're doing. The number that matters is the trend over time, "
            "so re-test in a few weeks to see how interventions move it."
        )
    delta = result.cardio_fitness_age - result.age
    return (
        f"Your reading came back {delta} years above your age. Most often this means the "
        "baseline wasn't truly rested (caffeine, stress, sitting at a desk). "
        "Try re-testing first thing tomorrow morning before getting out of bed. "
        "What matters is the trend over multiple readings, not the single number."
    )


def coach(result: TestResult, previous: TestRecord | None = None) -> str:
    """Generate a personalised coach paragraph. Returns fallback on any error.

    If `previous` is provided, the coaching includes a trend comparison.
    """
    api_key = os.environ.get("ASI1_API_KEY")
    if not api_key:
        return _fallback(result, previous)

    try:
        client = OpenAI(base_url=ASI1_BASE_URL, api_key=api_key)
        resp = client.chat.completions.create(
            model=os.environ.get("ASI1_MODEL", "asi1"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(result, previous)},
            ],
            temperature=0.4,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or _fallback(result, previous)
    except Exception:
        return _fallback(result, previous)

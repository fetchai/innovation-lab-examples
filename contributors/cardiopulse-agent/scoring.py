"""
Cardio fitness scoring.

Given the BPM samples from each phase of the test, compute:
- Resting HR (median of last 60s of baseline)
- Orthostatic delta (peak BPM in stand-up phase minus resting HR)
- Breathing-driven HR variance (stdev of BPM during paced breathing)
- A composite "Cardio Fitness Age" estimate adjusted from chronological age

The age estimate is rough (±5 years). It's meant for trend tracking — the
absolute number shouldn't be taken as a clinical reading.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

# Age-norm bands for resting HR. Numbers drawn from ACSM / AHA general
# guidelines. These are coarse buckets, not clinical thresholds.
RHR_NORMS: dict[str, tuple[int, int, int, int]] = {
    # bucket -> (excellent_at_or_below, good, average, anything-above = below avg)
    "20-29": (60, 65, 70, 75),
    "30-39": (62, 67, 72, 77),
    "40-49": (64, 69, 74, 79),
    "50-59": (66, 71, 76, 81),
    "60+": (68, 73, 78, 83),
}


@dataclass
class TestResult:
    age: int
    resting_hr: int
    orthostatic_delta: int
    breathing_variance: float
    cardio_fitness_age: int
    rhr_grade: str
    verdict: str
    quality_note: str | None = None


def _bucket(age: int) -> str:
    if age < 30:
        return "20-29"
    if age < 40:
        return "30-39"
    if age < 50:
        return "40-49"
    if age < 60:
        return "50-59"
    return "60+"


def _rhr_grade(rhr: int, age: int) -> str:
    excellent, good, average, _ = RHR_NORMS[_bucket(age)]
    if rhr <= excellent:
        return "excellent"
    if rhr <= good:
        return "good"
    if rhr <= average:
        return "typical"
    # "elevated", not "below average" — the old label read as if the NUMBER
    # was low, when a high resting HR is the unfavourable direction.
    return "elevated"


def compute(
    age: int,
    baseline_bpm: list[int],
    orthostatic_bpm: list[int],
    breathing_bpm: list[int],
) -> TestResult:
    if len(baseline_bpm) < 5:
        raise ValueError(
            "Not enough baseline data. Make sure the BLE bridge is streaming."
        )

    # Resting HR: median of the last ~60s of baseline (steadier than mean).
    tail = baseline_bpm[-60:] if len(baseline_bpm) >= 60 else baseline_bpm
    rhr = int(statistics.median(tail))

    # Orthostatic delta: peak BPM after standing minus resting HR.
    if orthostatic_bpm:
        ortho_peak = max(orthostatic_bpm)
        ortho_delta = max(0, ortho_peak - rhr)
    else:
        ortho_delta = 0

    # Breathing variance: stdev of BPM during paced breathing — proxy for
    # respiratory sinus arrhythmia (RSA).
    breath_var = statistics.stdev(breathing_bpm) if len(breathing_bpm) > 1 else 0.0

    # Composite "fitness age" adjustment relative to chronological age.
    # Each adjustment is small — the metric tracks trends more than absolutes.
    adjust = 0

    if rhr < 55:
        adjust -= 5
    elif rhr < 60:
        adjust -= 3
    elif rhr < 65:
        adjust -= 1
    elif rhr > 80:
        adjust += 5
    elif rhr > 75:
        adjust += 3

    if ortho_delta >= 25:
        adjust -= 2
    elif ortho_delta < 8:
        adjust += 3

    if breath_var > 5:
        adjust -= 2
    elif breath_var < 1.5:
        adjust += 2

    cardio_age = max(18, age + adjust)

    rhr_grade = _rhr_grade(rhr, age)

    if cardio_age < age - 2:
        verdict = (
            f"Your cardiovascular function is reading "
            f"{age - cardio_age} years younger than your chronological age."
        )
    elif cardio_age > age + 2:
        verdict = (
            f"Your cardiovascular function is reading "
            f"{cardio_age - age} years older than your chronological age. "
            "Room to improve."
        )
    else:
        verdict = (
            "Your cardiovascular function is roughly aligned with your "
            "chronological age."
        )

    # Data-quality detection: a visibly bad baseline should LOWER our
    # confidence rather than silently produce a scary score.
    notes: list[str] = []
    if rhr >= 90:
        notes.append(
            "Your baseline HR was unusually high for seated rest — stress, "
            "caffeine, talking, or moving around just before the test commonly "
            "inflate it. Treat this score as a low-confidence reading and "
            "re-test when you're calm and have been seated for 10+ minutes."
        )
    if len(baseline_bpm) < 90:
        notes.append(
            "Fewer heart-rate samples arrived than expected during the "
            "baseline — the watch broadcast may have dropped mid-test."
        )
    quality_note = " ".join(notes) if notes else None

    return TestResult(
        age=age,
        resting_hr=rhr,
        orthostatic_delta=ortho_delta,
        breathing_variance=round(breath_var, 1),
        cardio_fitness_age=cardio_age,
        rhr_grade=rhr_grade,
        verdict=verdict,
        quality_note=quality_note,
    )


def format_result(r: TestResult) -> str:
    """User-facing result block. Every number ships with its typical range so
    the reader can judge it without prior knowledge."""
    _, _, average, _ = RHR_NORMS[_bucket(r.age)]

    lines = [
        "**Cardio Fitness Test — Results**",
        "",
        f"**Cardio Fitness Age: {r.cardio_fitness_age}** (you are {r.age})",
        "",
        r.verdict,
        "",
        "**Key readings**",
        f"- Resting HR: **{r.resting_hr} bpm** — {r.rhr_grade}. "
        f"A well-rested value for your age is typically under {average} bpm.",
        f"- Standing response: **+{r.orthostatic_delta} bpm** — "
        "a typical jump on standing is +10 to +30 bpm.",
        f"- Breathing-driven HR variation: **{r.breathing_variance} bpm** — "
        "during slow paced breathing, roughly 3-8 bpm is common.",
    ]

    if r.quality_note:
        lines += ["", f"⚠️ **Data quality:** {r.quality_note}"]

    lines += [
        "",
        "_Estimates carry roughly ±5 years of uncertainty. The trend across "
        "repeated tests matters far more than any single number._",
    ]
    return "\n".join(lines)

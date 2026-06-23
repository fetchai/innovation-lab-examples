"""
Offline smoke test for scoring.py.

Generates synthetic BPM data for each phase, runs the scoring engine, and
prints the formatted result. Useful for sanity-checking changes to the
scoring formulas without needing a real watch.

    python test_scoring.py
"""

from __future__ import annotations

import random

import scoring

random.seed(42)


def synth_baseline(rhr: int, n: int = 120, jitter: int = 2) -> list[int]:
    """Resting BPM hovering around `rhr` with small jitter."""
    return [rhr + random.randint(-jitter, jitter) for _ in range(n)]


def synth_orthostatic(rhr: int, peak_delta: int, n: int = 30) -> list[int]:
    """BPM rises sharply on standing, then partially recovers."""
    out = []
    for i in range(n):
        # Rise over first 5 samples, plateau, then slight recovery.
        if i < 5:
            out.append(rhr + (peak_delta * i // 5))
        elif i < 20:
            out.append(rhr + peak_delta + random.randint(-2, 2))
        else:
            out.append(rhr + peak_delta - (i - 20))
    return out


def synth_breathing(rhr: int, swing: int, n: int = 30) -> list[int]:
    """BPM oscillates with the breath cycle (proxy for RSA)."""
    import math

    return [int(rhr + swing * math.sin(2 * math.pi * i / 10)) for i in range(n)]


def run_case(label: str, age: int, rhr: int, ortho_peak: int, breath_swing: int):
    print(f"\n=== {label} (age={age}, rhr={rhr}) ===")
    baseline = synth_baseline(rhr)
    ortho = synth_orthostatic(rhr, ortho_peak)
    breath = synth_breathing(rhr, breath_swing)

    result = scoring.compute(
        age=age,
        baseline_bpm=baseline,
        orthostatic_bpm=ortho,
        breathing_bpm=breath,
    )
    print(scoring.format_result(result))


def main() -> None:
    run_case("Fit 30-year-old", age=30, rhr=52, ortho_peak=22, breath_swing=6)
    run_case("Average 30-year-old", age=30, rhr=70, ortho_peak=15, breath_swing=3)
    run_case("Deconditioned 30-year-old", age=30, rhr=82, ortho_peak=6, breath_swing=1)
    run_case("Fit 50-year-old", age=50, rhr=58, ortho_peak=20, breath_swing=5)


if __name__ == "__main__":
    main()

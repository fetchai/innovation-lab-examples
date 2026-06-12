"""
HR-timeline chart generation.

Builds a single matplotlib figure showing BPM over the duration of a test,
with each phase (baseline / orthostatic / breathing) shaded distinctly so the
user can visually see their cardiac response. Saves the image to disk and
returns the path.

When a `TestResult` is supplied to `build()`, the chart is annotated with:
  - A horizontal dashed line at the computed Resting HR
  - A vertical bracket at the orthostatic peak showing the delta from RHR
  - A stats panel in the upper-right corner with the headline numbers + grades
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Sequence, TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")  # Headless backend — no display required.
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from history import TestRecord
    from scoring import TestResult

ASSETS_DIR = Path(__file__).parent / "assets"


def build(
    baseline_samples: Sequence[tuple[float, int]],
    orthostatic_samples: Sequence[tuple[float, int]],
    breathing_samples: Sequence[tuple[float, int]],
    output_path: Path | None = None,
    result: "TestResult | None" = None,
) -> Path:
    """
    Render an HR timeline with phase shading.

    Each `*_samples` argument is a sequence of (timestamp_seconds, bpm) tuples.
    The chart shifts the first timestamp to 0 so the x-axis reads as
    elapsed seconds.

    Returns the absolute path to the saved PNG.
    """
    ASSETS_DIR.mkdir(exist_ok=True)
    if output_path is None:
        output_path = ASSETS_DIR / "last_test.png"

    all_samples = (
        list(baseline_samples) + list(orthostatic_samples) + list(breathing_samples)
    )
    if not all_samples:
        # Empty test — generate a placeholder so the agent still has something to send.
        fig, ax = plt.subplots(figsize=(8, 4), dpi=110)
        ax.text(
            0.5,
            0.5,
            "No HR data collected",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=14,
            color="#888",
        )
        ax.set_axis_off()
        fig.savefig(output_path, bbox_inches="tight")
        plt.close(fig)
        return output_path

    t0 = all_samples[0][0]

    def normalise(samples):
        return [(t - t0, bpm) for t, bpm in samples]

    baseline_norm = normalise(baseline_samples)
    ortho_norm = normalise(orthostatic_samples)
    breath_norm = normalise(breathing_samples)

    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)

    # Phase boundaries
    if baseline_norm:
        b_end = baseline_norm[-1][0]
    else:
        b_end = 0
    if ortho_norm:
        o_end = ortho_norm[-1][0]
    else:
        o_end = b_end
    if breath_norm:
        br_end = breath_norm[-1][0]
    else:
        br_end = o_end

    # Background shading per phase
    ax.axvspan(0, b_end, color="#E3F2FD", alpha=0.6, label="_nolegend_")
    ax.axvspan(b_end, o_end, color="#FFF3E0", alpha=0.6, label="_nolegend_")
    ax.axvspan(o_end, br_end, color="#E8F5E9", alpha=0.6, label="_nolegend_")

    # Plot HR lines per phase with distinct colours
    if baseline_norm:
        xs, ys = zip(*baseline_norm)
        ax.plot(xs, ys, color="#1976D2", linewidth=1.8, label="Resting baseline")
    if ortho_norm:
        xs, ys = zip(*ortho_norm)
        ax.plot(xs, ys, color="#F57C00", linewidth=1.8, label="Standing")
    if breath_norm:
        xs, ys = zip(*breath_norm)
        ax.plot(xs, ys, color="#388E3C", linewidth=1.8, label="Paced breathing")

    # Phase labels at the top
    if b_end > 0:
        ax.text(
            b_end / 2,
            ax.get_ylim()[1] if False else 1.02,
            "Baseline",
            transform=ax.get_xaxis_transform(),
            ha="center",
            fontsize=10,
            color="#1976D2",
            fontweight="bold",
        )
    if o_end > b_end:
        ax.text(
            (b_end + o_end) / 2,
            1.02,
            "Stand",
            transform=ax.get_xaxis_transform(),
            ha="center",
            fontsize=10,
            color="#F57C00",
            fontweight="bold",
        )
    if br_end > o_end:
        ax.text(
            (o_end + br_end) / 2,
            1.02,
            "Breathe",
            transform=ax.get_xaxis_transform(),
            ha="center",
            fontsize=10,
            color="#388E3C",
            fontweight="bold",
        )

    # Mark orthostatic peak if present
    peak_t, peak_bpm = None, None
    if ortho_norm:
        peak_t, peak_bpm = max(ortho_norm, key=lambda p: p[1])
        ax.annotate(
            f"peak {peak_bpm} bpm",
            xy=(peak_t, peak_bpm),
            xytext=(peak_t + 5, peak_bpm + 6),
            fontsize=9,
            color="#333",
            arrowprops=dict(arrowstyle="->", color="#666", lw=0.8),
        )

    # --- Annotations driven by the scored result -----------------------------
    if result is not None:
        rhr = result.resting_hr

        # 1. Horizontal dashed line at the computed Resting HR.
        ax.axhline(
            y=rhr,
            color="#1976D2",
            linestyle="--",
            linewidth=1.1,
            alpha=0.65,
            zorder=2,
        )
        # Right-edge label so the line means something visually.
        x_right = ax.get_xlim()[1]
        ax.text(
            x_right * 0.985,
            rhr - 1.2,
            f"Resting HR  {rhr} bpm",
            color="#1976D2",
            fontsize=9,
            fontweight="semibold",
            ha="right",
            va="top",
            bbox=dict(
                facecolor="white",
                edgecolor="#1976D2",
                boxstyle="round,pad=0.25",
                alpha=0.85,
            ),
        )

        # 2. Vertical bracket at the orthostatic peak showing the delta.
        if peak_t is not None and peak_bpm is not None and result.orthostatic_delta > 0:
            bracket_x = (
                peak_t - 4
            )  # offset a bit left of the peak so it doesn't overlap
            # Stem of the bracket
            ax.annotate(
                "",
                xy=(bracket_x, peak_bpm),
                xytext=(bracket_x, rhr),
                arrowprops=dict(arrowstyle="-", color="#F57C00", linewidth=1.4),
            )
            # Tick marks at top and bottom
            tick_w = 2
            ax.plot(
                [bracket_x - tick_w, bracket_x + tick_w],
                [peak_bpm, peak_bpm],
                color="#F57C00",
                linewidth=1.4,
                zorder=3,
            )
            ax.plot(
                [bracket_x - tick_w, bracket_x + tick_w],
                [rhr, rhr],
                color="#F57C00",
                linewidth=1.4,
                zorder=3,
            )
            # Delta label
            mid_y = (rhr + peak_bpm) / 2
            ax.text(
                bracket_x - 5,
                mid_y,
                f"+{result.orthostatic_delta}\nbpm",
                color="#F57C00",
                fontsize=9,
                fontweight="semibold",
                ha="right",
                va="center",
            )

        # 3. Stats panel — small overlay in the upper-left.
        verdict_short = (
            "younger"
            if result.cardio_fitness_age < result.age
            else "aligned"
            if result.cardio_fitness_age == result.age
            else "older"
        )
        delta_years = abs(result.cardio_fitness_age - result.age)
        if verdict_short == "aligned":
            cardio_summary = f"= age {result.age}"
        elif verdict_short == "younger":
            cardio_summary = f"{delta_years}y younger"
        else:
            cardio_summary = f"{delta_years}y older"

        stats_text = (
            f"Cardio Age:   {result.cardio_fitness_age}  ({cardio_summary})\n"
            f"Resting HR:   {result.resting_hr} bpm  ({result.rhr_grade})\n"
            f"Orthostatic:  +{result.orthostatic_delta} bpm\n"
            f"Breathing:    {result.breathing_variance} bpm RSA"
        )
        ax.text(
            0.018,
            0.97,
            stats_text,
            transform=ax.transAxes,
            fontsize=9,
            family="monospace",
            verticalalignment="top",
            horizontalalignment="left",
            bbox=dict(
                facecolor="white",
                edgecolor="#999",
                boxstyle="round,pad=0.45",
                alpha=0.92,
            ),
        )

    ax.set_xlabel("Elapsed time (seconds)", fontsize=10)
    ax.set_ylabel("Heart rate (bpm)", fontsize=10)
    ax.set_title("Your HR across the cardio fitness test", fontsize=13, pad=18)
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)
    ax.grid(True, alpha=0.25, linestyle="--")

    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def build_png_bytes(
    baseline_samples: Sequence[tuple[float, int]],
    orthostatic_samples: Sequence[tuple[float, int]],
    breathing_samples: Sequence[tuple[float, int]],
    result: "TestResult | None" = None,
) -> bytes:
    """Render the chart and return raw PNG bytes — no disk writes.

    Use this when you want to upload the chart somewhere (Agentverse storage,
    imgur, S3) without saving locally first.
    """
    return _render_png_buf(
        baseline_samples, orthostatic_samples, breathing_samples, result
    ).getvalue()


def build_trend_png_bytes(records: "list[TestRecord]") -> bytes:
    """Render a trend chart showing Cardio Fitness Age + Resting HR over the
    last N tests. Returns PNG bytes. Returns empty bytes if fewer than 2
    records (nothing to trend yet).
    """
    if not records or len(records) < 2:
        return b""

    # Index x-axis as 1..N (test number) rather than dates — clearer in chat.
    xs = list(range(1, len(records) + 1))
    cardio_ages = [r.cardio_fitness_age for r in records]
    rhrs = [r.resting_hr for r in records]
    chronological_age = records[-1].age  # most recent test's chrono age

    fig, ax_left = plt.subplots(figsize=(7, 3.5), dpi=80)

    # Left axis: Cardio Fitness Age (blue line + dots)
    color_left = "#1976D2"
    ax_left.plot(
        xs,
        cardio_ages,
        color=color_left,
        marker="o",
        linewidth=2,
        label="Cardio Fitness Age",
    )
    ax_left.set_xlabel("Test number", fontsize=10)
    ax_left.set_ylabel("Cardio Fitness Age (years)", color=color_left, fontsize=10)
    ax_left.tick_params(axis="y", labelcolor=color_left)

    # Reference line: user's chronological age
    ax_left.axhline(
        y=chronological_age,
        color=color_left,
        linestyle=":",
        alpha=0.45,
        linewidth=1.0,
    )
    ax_left.text(
        xs[-1],
        chronological_age + 0.2,
        f"chronological age ({chronological_age})",
        color=color_left,
        fontsize=8,
        ha="right",
        va="bottom",
        alpha=0.75,
    )

    # Right axis: Resting HR (orange line + dots)
    color_right = "#F57C00"
    ax_right = ax_left.twinx()
    ax_right.plot(
        xs, rhrs, color=color_right, marker="s", linewidth=2, label="Resting HR"
    )
    ax_right.set_ylabel("Resting HR (bpm)", color=color_right, fontsize=10)
    ax_right.tick_params(axis="y", labelcolor=color_right)

    # Annotate the latest point with both values
    latest_x = xs[-1]
    latest_ca = cardio_ages[-1]
    latest_rhr = rhrs[-1]
    ax_left.annotate(
        f"{latest_ca}",
        xy=(latest_x, latest_ca),
        xytext=(6, 6),
        textcoords="offset points",
        color=color_left,
        fontsize=10,
        fontweight="bold",
    )
    ax_right.annotate(
        f"{latest_rhr}",
        xy=(latest_x, latest_rhr),
        xytext=(6, -14),
        textcoords="offset points",
        color=color_right,
        fontsize=10,
        fontweight="bold",
    )

    # Trend direction text in upper-left
    first_ca, last_ca = cardio_ages[0], cardio_ages[-1]
    first_rhr, last_rhr = rhrs[0], rhrs[-1]
    ca_delta = last_ca - first_ca
    rhr_delta = last_rhr - first_rhr

    if ca_delta < 0:
        ca_trend = f"Cardio Age: {abs(ca_delta)} years younger"
    elif ca_delta > 0:
        ca_trend = f"Cardio Age: {ca_delta} years older"
    else:
        ca_trend = "Cardio Age: stable"

    rhr_dir = "down" if rhr_delta < 0 else "up" if rhr_delta > 0 else "flat"
    rhr_trend = f"Resting HR: {rhr_dir} {abs(rhr_delta)} bpm"

    summary = f"Across {len(records)} tests\n{ca_trend}\n{rhr_trend}"
    ax_left.text(
        0.02,
        0.97,
        summary,
        transform=ax_left.transAxes,
        fontsize=8,
        family="monospace",
        verticalalignment="top",
        bbox=dict(
            facecolor="white", edgecolor="#999", boxstyle="round,pad=0.35", alpha=0.9
        ),
    )

    ax_left.set_title("Your trend across recent tests", fontsize=12, pad=10)
    ax_left.grid(True, alpha=0.25, linestyle="--")
    ax_left.set_xticks(xs)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def build_data_uri(
    baseline_samples: Sequence[tuple[float, int]],
    orthostatic_samples: Sequence[tuple[float, int]],
    breathing_samples: Sequence[tuple[float, int]],
    result: "TestResult | None" = None,
) -> str:
    """Render the same chart and return it as a base64 data URI.

    Suitable for embedding directly in a markdown image tag inside a chat
    message: `![chart](data:image/png;base64,...)`. No upload needed.

    We re-render at slightly smaller size + lower DPI than build() to keep the
    encoded payload modest (~40-60 KB) so chat protocols don't choke.
    """
    buf = _render_png_buf(
        baseline_samples, orthostatic_samples, breathing_samples, result
    )
    if buf.getbuffer().nbytes == 0:
        return ""
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _render_png_buf(
    baseline_samples: Sequence[tuple[float, int]],
    orthostatic_samples: Sequence[tuple[float, int]],
    breathing_samples: Sequence[tuple[float, int]],
    result: "TestResult | None" = None,
) -> "io.BytesIO":
    """Internal: render the chart into an in-memory BytesIO buffer.

    Returns an empty buffer if there's no sample data to plot.
    """
    all_samples = (
        list(baseline_samples) + list(orthostatic_samples) + list(breathing_samples)
    )
    if not all_samples:
        return io.BytesIO()

    t0 = all_samples[0][0]

    def normalise(samples):
        return [(t - t0, bpm) for t, bpm in samples]

    baseline_norm = normalise(baseline_samples)
    ortho_norm = normalise(orthostatic_samples)
    breath_norm = normalise(breathing_samples)

    fig, ax = plt.subplots(figsize=(7, 3.3), dpi=80)

    b_end = baseline_norm[-1][0] if baseline_norm else 0
    o_end = ortho_norm[-1][0] if ortho_norm else b_end
    br_end = breath_norm[-1][0] if breath_norm else o_end

    ax.axvspan(0, b_end, color="#E3F2FD", alpha=0.6)
    ax.axvspan(b_end, o_end, color="#FFF3E0", alpha=0.6)
    ax.axvspan(o_end, br_end, color="#E8F5E9", alpha=0.6)

    if baseline_norm:
        xs, ys = zip(*baseline_norm)
        ax.plot(xs, ys, color="#1976D2", linewidth=1.6, label="Resting baseline")
    if ortho_norm:
        xs, ys = zip(*ortho_norm)
        ax.plot(xs, ys, color="#F57C00", linewidth=1.6, label="Standing")
    if breath_norm:
        xs, ys = zip(*breath_norm)
        ax.plot(xs, ys, color="#388E3C", linewidth=1.6, label="Paced breathing")

    if result is not None:
        ax.axhline(
            y=result.resting_hr,
            color="#1976D2",
            linestyle="--",
            linewidth=1.0,
            alpha=0.6,
        )
        stats = (
            f"Cardio Age: {result.cardio_fitness_age} (age {result.age})\n"
            f"RHR: {result.resting_hr} ({result.rhr_grade})\n"
            f"Ortho: +{result.orthostatic_delta} bpm\n"
            f"RSA: {result.breathing_variance} bpm"
        )
        ax.text(
            0.018,
            0.97,
            stats,
            transform=ax.transAxes,
            fontsize=8,
            family="monospace",
            verticalalignment="top",
            bbox=dict(
                facecolor="white",
                edgecolor="#999",
                boxstyle="round,pad=0.3",
                alpha=0.92,
            ),
        )

    ax.set_xlabel("Elapsed time (s)", fontsize=9)
    ax.set_ylabel("Heart rate (bpm)", fontsize=9)
    ax.set_title("Your HR across the cardio fitness test", fontsize=11)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    ax.grid(True, alpha=0.25, linestyle="--")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf

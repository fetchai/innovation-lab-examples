from __future__ import annotations

from typing import Any

from app.models.synthesis import SynthesisResult


def synthesis_to_markdown(syn: SynthesisResult, structured: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("## Summary")
    lines.append(syn.summary or "_No summary._")
    if syn.next_steps:
        lines.append("\n## Next steps")
        for s in syn.next_steps:
            lines.append(f"- {s}")
    if syn.estimated_cost_range:
        lo, hi = syn.estimated_cost_range
        lines.append("\n## Rough cost band (parts + simple DIY context)")
        lines.append(f"- ${lo:.0f} – ${hi:.0f} (heuristic, not a quote)")
    tut = structured.get("tutorials")
    vids = tut.get("videos", []) if isinstance(tut, dict) else []
    if vids:
        lines.append("\n## Videos")
        for v in vids[:5]:
            title = v.get("title", "")
            url = v.get("url", "")
            if url:
                lines.append(f"- [{title}]({url})")
            else:
                lines.append(f"- {title}")
    return "\n".join(lines).strip()

"""
An Example of a runtime controller generating each turn instructions
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class SteeringInputs:
    goal: str                                  # this turn's objective
    style: str = "concise"                     # terse, detailed, crisp, etc.
    max_cites: int = 2                         # runtime knob
    tenant_hint: Optional[str] = None          # "Answer for EU employees only"
    corrective: Optional[str] = None           # "Last reply missed field X; include it"
    confidence_range: Tuple[float, float] = (0.6, 0.9)


def build_turn_instruction(s: SteeringInputs) -> str:
    parts = [
        f"Goal: {s.goal}",
        f"Style: {s.style}",
        (
            "Constraints: "
            f"include at most {s.max_cites} citations; "
            "refuse medical/legal advice; "
            "if info is missing, ask one targeted question; "
            f"return 'confidence' between {s.confidence_range[0]} and {s.confidence_range[1]}."
        )
    ]
    
    if s.tenant_hint:
        parts.append(f"Tenant: {s.tenant_hint}")
    
    if s.corrective:
        parts.append(f"Correction: {s.corrective}")
    
    return "\n".join(parts)


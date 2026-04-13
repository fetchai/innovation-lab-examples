from __future__ import annotations

from typing import Any


def merge_structured(
    diagnosis: dict[str, Any],
    sourcing: dict[str, Any],
    tutorials: dict[str, Any],
    synthesis: dict[str, Any],
) -> dict[str, Any]:
    return {
        "diagnosis": diagnosis,
        "sourcing": sourcing,
        "tutorials": tutorials,
        "synthesis": synthesis,
    }

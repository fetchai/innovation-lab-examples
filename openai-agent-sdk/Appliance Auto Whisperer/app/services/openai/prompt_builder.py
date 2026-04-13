from pathlib import Path


def _prompts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts"


def load_text(name: str) -> str:
    p = _prompts_dir() / name
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def vision_diagnosis_prompt() -> str:
    return (
        load_text("vision_diagnosis.txt") or "Describe likely faults and safety notes."
    )


def repair_cost_rules() -> str:
    return load_text("repair_cost_rules.txt") or "Use conservative cost ranges."


def synthesis_style() -> str:
    return load_text("synthesis_style.txt") or "Be concise and actionable."

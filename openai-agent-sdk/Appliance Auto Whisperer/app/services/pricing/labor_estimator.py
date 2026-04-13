from app.services.pricing.heuristics import complexity_score


def estimate_labor_hours(appliance_type: str, part_count: int) -> float:
    base = 1.0 + 0.25 * max(0, part_count - 1)
    return base * (1.0 + 0.05 * complexity_score(appliance_type))

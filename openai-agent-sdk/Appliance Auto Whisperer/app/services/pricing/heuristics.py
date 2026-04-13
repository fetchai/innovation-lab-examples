def complexity_score(appliance_type: str) -> float:
    t = appliance_type.lower()
    if "refrigerator" in t or "fridge" in t:
        return 1.2
    if "dishwasher" in t:
        return 1.0
    return 0.8


def rough_part_cost_band(part_count: int) -> tuple[float, float]:
    low = 25.0 + 15.0 * max(0, part_count - 1)
    high = 120.0 + 45.0 * max(0, part_count - 1)
    return (low, high)

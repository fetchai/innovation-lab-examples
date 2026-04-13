from app.services.pricing.labor_estimator import estimate_labor_hours


def test_estimate_labor_hours_positive() -> None:
    h = estimate_labor_hours("refrigerator", 2)
    assert h > 0

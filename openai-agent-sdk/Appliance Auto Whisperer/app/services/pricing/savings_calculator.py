def diy_savings(
    pro_quote_usd: float,
    parts_usd: float,
    labor_hours: float,
    hourly_rate: float = 95.0,
) -> float:
    pro_like = parts_usd + labor_hours * hourly_rate
    return max(0.0, pro_like - pro_quote_usd)

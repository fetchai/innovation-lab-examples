"""Form submission argument builder."""

from tripmate.mcp_args import prepare_mcp_args
from tripmate.utils import add_days, normalize_future_date


def build_search_args(form: dict) -> tuple[str, dict]:
    trip = form.get("trip_type", "flight")
    adults = str(int(form.get("adults") or 1))
    dest = form["destination"].strip()
    origin = (form.get("origin") or dest).strip()
    date_from = normalize_future_date(form["departure_date"])
    date_to = (
        normalize_future_date(form["return_date"]) if form.get("return_date") else None
    )

    if trip == "hotel":
        return "search_only_hotel", prepare_mcp_args(
            "search_only_hotel",
            {
                "destination": dest,
                "date_from": date_from,
                "date_to": date_to or add_days(date_from, 1),
                "adults": adults,
                "lang": "en",
            },
        )
    if trip == "package":
        return "search_flight_and_hotel_package", prepare_mcp_args(
            "search_flight_and_hotel_package",
            {
                "origin": origin,
                "destination": dest,
                "date_from": date_from,
                "date_to": date_to,
                "nights": 3,
                "adults": adults,
                "lang": "en",
            },
        )
    args = prepare_mcp_args(
        "search_flights",
        {
            "departure": origin,
            "arrival": dest,
            "start_date": date_from,
            "adults": int(adults),
            "language": "en",
        },
    )
    if date_to:
        args["end_date"] = date_to
    return "search_flights", args

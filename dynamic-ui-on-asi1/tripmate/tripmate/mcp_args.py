"""Normalize arguments before MCP tool calls."""

from tripmate.utils import add_days, normalize_future_date, to_iata


def prepare_mcp_args(tool_name: str, args: dict) -> dict:
    args = dict(args)
    if tool_name == "search_flight_and_hotel_package":
        args["origin"] = to_iata(str(args.get("origin", "")))
        args["destination"] = to_iata(str(args.get("destination", "")))
        if args.get("date_from"):
            args["date_from"] = normalize_future_date(str(args["date_from"]))
        if args.get("date_to"):
            args["date_to"] = normalize_future_date(str(args["date_to"]))
        elif args.get("date_from"):
            nights = int(args.pop("nights", 3) or 3)
            args["date_to"] = add_days(args["date_from"], nights)
        args["adults"] = str(args.get("adults", "1"))
        args.setdefault("lang", "en")
    elif tool_name == "search_only_hotel":
        args["destination"] = to_iata(str(args.get("destination", "")))
        if args.get("date_from"):
            args["date_from"] = normalize_future_date(str(args["date_from"]))
        if args.get("date_to"):
            args["date_to"] = normalize_future_date(str(args["date_to"]))
        elif args.get("date_from"):
            args["date_to"] = add_days(args["date_from"], 1)
        args["adults"] = str(args.get("adults", "1"))
        args.setdefault("lang", "en")
    elif tool_name == "search_flights":
        if args.get("departure"):
            args["departure"] = to_iata(str(args["departure"]))
        if args.get("arrival"):
            args["arrival"] = to_iata(str(args["arrival"]))
        if args.get("start_date"):
            args["start_date"] = normalize_future_date(str(args["start_date"]))
        if args.get("end_date"):
            args["end_date"] = normalize_future_date(str(args["end_date"]))
        if "adults" in args:
            args["adults"] = int(args["adults"])
    elif tool_name == "select_hotel_options":
        if "search_id" in args:
            args["search_id"] = int(args["search_id"])
        if "hotel_internal_id" in args:
            args["hotel_internal_id"] = int(args["hotel_internal_id"])
    return args

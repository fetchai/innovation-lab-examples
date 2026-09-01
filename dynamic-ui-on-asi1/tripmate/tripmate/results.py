"""Parse MCP results and build carousel payloads."""

import re
from urllib.parse import quote_plus

from tripmate.config import CITY_IATA
from tripmate.utils import parse_mcp_json


def index_search_results(mcp_text: str) -> dict:
    data = parse_mcp_json(mcp_text)
    if not data:
        return {}
    index: dict = {}
    for f in data.get("flights", []):
        fid = f"flight_{f.get('flight_number', len(index) + 1)}"
        index[fid] = f
    for p in data.get("products_summary", []):
        idx = p.get("index", len(index) + 1)
        index[f"pkg_{idx}"] = p
        index[f"hotel_{idx}"] = p
    return index


def extract_book_url(item: dict) -> str:
    for key in ("deeplink", "book_url", "booking_link", "url"):
        val = item.get(key, "")
        if isinstance(val, str) and val.startswith("http"):
            return val
        m = re.search(r"\((https?://[^)]+)\)", str(val))
        if m:
            return m.group(1)
    return ""


METRO_LABELS = {
    "LON": "London",
    "ROM": "Rome",
    "PAR": "Paris",
    "MAD": "Madrid",
    "BCN": "Barcelona",
    "BER": "Berlin",
    "AMS": "Amsterdam",
}


def _destination_label(destination: str) -> str:
    if not destination:
        return "your destination"
    dest = destination.strip().upper()
    if dest in METRO_LABELS:
        return METRO_LABELS[dest]
    for city, iata in CITY_IATA.items():
        if iata == dest:
            return city.title()
    if len(dest) == 3 and dest.isalpha():
        return dest
    return destination.strip().title()


def _hotel_image(hotel: dict) -> str:
    image = hotel.get("image")
    if image:
        return image
    name = quote_plus((hotel.get("name") or "Hotel")[:24])
    return f"https://placehold.co/400x300?text={name}"


def _hotel_subtitle(hotel: dict) -> str:
    parts = []
    stars = hotel.get("stars")
    if stars:
        parts.append(f"{int(stars)}★")
    distance = hotel.get("distance_km")
    if distance is not None:
        parts.append(f"{distance} km from centre")
    return " · ".join(parts) if parts else "Hotel"


def _hotel_price_text(hotel: dict, nights: int = 1) -> str:
    currency = hotel.get("currency", "")
    total = hotel.get("price_total")
    if total is None:
        return ""
    nights = max(int(nights or 1), 1)
    per_night = float(total) / nights
    amount = f"{per_night:.0f}" if per_night == int(per_night) else f"{per_night:.2f}"
    return f"{currency} {amount}/night".strip()


def hotels_carousel(data: dict, destination: str) -> dict:
    items = []
    nights = (data.get("search_params") or {}).get("nights") or 1
    dest_label = _destination_label(destination)
    for h in data.get("products_summary", [])[:5]:
        idx = h.get("index", len(items) + 1)
        hid = f"hotel_{idx}"
        items.append(
            {
                "id": hid,
                "image": _hotel_image(h),
                "title": h.get("name", f"Hotel {idx}"),
                "subtitle": _hotel_subtitle(h),
                "secondary_text": _hotel_price_text(h, nights),
                "primary_cta": {
                    "label": "Pick",
                    "selection": {"hotel_id": hid},
                },
            }
        )
    return {
        "title": f"Hotels in {dest_label}",
        "subtitle": "Pick one to see fare options",
        "style": "slide",
        "items": items,
    }


def packages_carousel(data: dict, subtitle: str) -> dict:
    items = []
    search_id = data.get("search_id", "")
    for p in data.get("products_summary", [])[:5]:
        idx = p.get("index", 0)
        price = f"{p.get('currency', '')} {p.get('price_total', '')}".strip()
        carrier = p.get("carrier", "")
        direct = "Direct" if p.get("flight_direct") else "Stops"
        items.append(
            {
                "id": f"pkg_{idx}",
                "image": p.get("image"),
                "title": p.get("name", f"Package {idx}"),
                "subtitle": f"{'⭐' * int(p.get('stars', 0))} · {carrier} · {direct}",
                "badges": [{"label": f"{p.get('rating', '')}/100", "variant": "info"}],
                "secondary_text": price,
                "primary_cta": {
                    "label": "View & Book",
                    "selection": {
                        "action": "pick_package",
                        "package_id": f"pkg_{idx}",
                        "search_id": str(search_id),
                        "hotel_internal_id": str(p.get("internal_id_hotel", "")),
                    },
                },
            }
        )
    return {"title": "Flight + Hotel packages", "subtitle": subtitle, "items": items}


def _airline_logo(airline: str) -> str:
    initials = (
        "".join(word[0] for word in (airline or "FL").split()[:2]).upper() or "FL"
    )
    return f"https://placehold.co/48x48?text={initials}"


def _flight_subtitle(flight: dict) -> str:
    outbound = flight.get("outbound", "")
    ret = flight.get("return", "")
    stops = flight.get("stops", "Direct")
    duration = flight.get("duration", "")
    price = flight.get("price", "")
    parts = []
    if outbound:
        parts.append(outbound if not ret else f"{outbound} · Return: {ret}")
    if stops:
        parts.append(stops if isinstance(stops, str) else "Direct")
    if duration:
        parts.append(duration)
    if price:
        parts.append(price)
    return " · ".join(parts) if parts else "Flight option"


def flights_json_carousel(data: dict, subtitle: str) -> dict:
    items = []
    for f in data.get("flights", [])[:5]:
        fid = f"flight_{f.get('flight_number', len(items) + 1)}"
        airline = f.get("airline", "Flight")
        items.append(
            {
                "id": fid,
                "logo": _airline_logo(airline),
                "title": airline,
                "subtitle": _flight_subtitle(f),
                "primary_cta": {
                    "label": "Select",
                    "selection": {"offer_id": fid},
                },
            }
        )
    return {
        "title": "Choose a flight",
        "subtitle": subtitle,
        "style": "slide",
        "root_cta": {"label": "More options", "selection": {"action": "more_options"}},
        "items": items,
    }


def results_to_carousel(
    tool_name: str, mcp_text: str, subtitle: str
) -> tuple[str, dict] | None:
    data = parse_mcp_json(mcp_text)
    if not data or data.get("success") is False:
        return None
    if data.get("products_summary"):
        if tool_name == "search_only_hotel":
            destination = subtitle or (data.get("search_params") or {}).get(
                "destination", ""
            )
            return "carousel", hotels_carousel(data, destination)
        if "package" in tool_name or tool_name == "search_flight_and_hotel_package":
            return "carousel", packages_carousel(data, subtitle)
    if data.get("flights"):
        return "carousel", flights_json_carousel(data, subtitle)
    return None


def summary_rows_from_item(item: dict) -> list[dict]:
    skip = {"image", "internal_id_hotel", "carrier_id", "price_amount", "price_format"}
    rows = []
    for k, v in item.items():
        if k in skip or v in (None, "", []):
            continue
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        rows.append({"label": k.replace("_", " ").title(), "value": str(v)})
    return rows[:10]


def extract_booking_from_hotel_detail(data: dict) -> tuple[str, str]:
    """Return (title, book_url) from select_hotel_options response."""
    title = data.get("hotel_name") or data.get("name") or "Your package"
    for key in ("booking_link", "deeplink", "book_url", "url"):
        val = data.get(key, "")
        if isinstance(val, str) and "http" in val:
            m = re.search(r"(https?://\S+)", val)
            if m:
                return title, m.group(1).rstrip(")")
    rooms = data.get("rooms") or data.get("available_rooms") or []
    if rooms and isinstance(rooms[0], dict):
        for key in ("deeplink", "booking_link", "book_url"):
            val = rooms[0].get(key, "")
            if isinstance(val, str) and "http" in val:
                m = re.search(r"(https?://\S+)", val)
                if m:
                    return title, m.group(1).rstrip(")")
    pricing_id = data.get("pricing_id")
    rate_id = data.get("rate_id")
    if rooms and isinstance(rooms[0], dict):
        pricing_id = pricing_id or rooms[0].get("pricing_id")
        rate_id = rate_id or rooms[0].get("rate_id")
    return title, ""

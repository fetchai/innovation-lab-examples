# duffel_tools.py
"""
Duffel tool adapters used by the LangGraph agent.

Fixes included:
- duffel_get_offer_with_services now returns offer_passengers (IDs & types).
- duffel_create_order auto-maps offer_passenger IDs to submitted passengers if missing.
- HOLD-first by default; set pay_with_balance_now=True for instant ticketing.
- Itinerary formatting is robust.
- USDC and optional FET conversions preserved.

Tools:
- duffel_search_offers(...)
- duffel_get_offer_with_services(...)
- duffel_create_order(...)
- duffel_pay_hold_order(...)
- duffel_get_order(...)
- duffel_create_order_cancellation(...)
- duffel_confirm_order_cancellation(...)
"""

from __future__ import annotations

import os
import re
import time
import smtplib
from typing import Any, Dict, List, Optional, Tuple
from email.message import EmailMessage

import httpx

try:
    from langchain_core.tools import tool as _tool
except Exception:  # pragma: no cover
    def _tool(f):
        return f


# -----------------------------
# Environment / constants
# -----------------------------
_DUFFEL_TOKEN = os.getenv("DUFFEL_TOKEN", "")
_DUFFEL_BASE = "https://api.duffel.com"
_TIMEOUT = 30.0

# FX (USDC) via FreeCurrencyAPI (base USD → invert for USD per CUR)
_FREECURRENCY_KEY = os.getenv("FREECURRENCYAPI_KEY", "")
# Optional: USD per 1 FET (e.g., 0.80 means 1 FET = $0.80 → 1 USD = 1.25 FET)
_FET_USD_PRICE = os.getenv("FET_USD_PRICE")

_FX_CACHE: Dict[str, Tuple[float, float]] = {}
_PRICE_CACHE: Dict[str, Tuple[float, float]] = {}


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_DUFFEL_TOKEN}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _fmt_time(ts: str | None) -> str:
    """Show up to minutes: 'YYYY-MM-DD HH:MM' (Duffel returns ISO8601)."""
    s = (ts or "").replace("T", " ").replace("Z", "")
    return re.sub(r"(\d{2}:\d{2}):\d{2}$", r"\1", s)


def _get_usd_per(cur: str) -> Optional[float]:
    if not cur:
        return None
    cur = cur.upper()
    if cur in ("USD", "USDC"):
        return 1.0

    now = time.time()
    cached = _FX_CACHE.get(cur)
    if cached and cached[1] > now:
        return cached[0]

    if not _FREECURRENCY_KEY:
        return None

    try:
        r = httpx.get(
            "https://api.freecurrencyapi.com/v1/latest",
            params={"apikey": _FREECURRENCY_KEY, "currencies": cur},
            timeout=10.0,
        )
        r.raise_for_status()
        data = (r.json() or {}).get("data") or {}
        usd_to_cur = float(data.get(cur))
        if usd_to_cur <= 0:
            return None
        usd_per_cur = 1.0 / usd_to_cur
        _FX_CACHE[cur] = (usd_per_cur, now + 60.0)
        return usd_per_cur
    except Exception:
        return None


def _to_usdc(amount: Any, currency: str) -> Optional[float]:
    try:
        amt = float(amount)
    except Exception:
        return None
    usd_per = _get_usd_per(currency)
    if not usd_per:
        return None
    return amt * usd_per


def _fet_per_usd() -> Optional[float]:
    now = time.time()
    cached = _PRICE_CACHE.get("FET_USD")
    if cached and cached[1] > now:
        return cached[0]
    if not _FET_USD_PRICE:
        return None
    try:
        usd_per_fet = float(_FET_USD_PRICE)
        if usd_per_fet <= 0:
            return None
        fet_per_usd = 1.0 / usd_per_fet
        _PRICE_CACHE["FET_USD"] = (fet_per_usd, now + 300.0)
        return fet_per_usd
    except Exception:
        return None


def _apply_conversions(summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds:
      - original_amount/original_currency (when conversion succeeds)
      - total_amount_usdc
      - total_amount_fet (if env price available)
    Never deletes existing keys.
    """
    out = dict(summary)
    amt = summary.get("total_amount")
    cur = (summary.get("total_currency") or "").upper()
    usd = _to_usdc(amt, cur) if (amt is not None and cur) else None
    if usd is not None:
        out["original_amount"] = amt
        out["original_currency"] = cur
        out["total_amount_usdc"] = round(usd, 2)
        fet_per_usd = _fet_per_usd()
        if fet_per_usd:
            out["total_amount_fet"] = round(usd * fet_per_usd, 6)
    return out


def _smtp_enabled() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))


def _send_email(to_addr: str, subject: str, body: str) -> bool:
    if not _smtp_enabled():
        return False
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM", user)
    from_name = os.getenv("SMTP_FROM_NAME", "Flights Agent")
    try:
        msg = EmailMessage()
        msg["From"] = f"{from_name} <{from_addr}>"
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception:
        return False


def _format_itinerary(slices: List[Dict[str, Any]]) -> str:
    """
    Builds a compact itinerary string like:
      'LAX→SFO 2026-01-25 09:15 → 10:45 | SFO→SEA 12:10 → 13:55'
    Falls back to route-only if segment times are missing.
    """
    legs: List[str] = []
    for sl in slices or []:
        segs = sl.get("segments") or []
        if not segs:
            ori = ((sl.get("origin") or {}).get("iata_code")) or ""
            dst = ((sl.get("destination") or {}).get("iata_code")) or ""
            s = f"{ori}→{dst}".strip("→")
            if s:
                legs.append(s)
            continue
        a = (segs[0].get("origin") or {}).get("iata_code") or ""
        b = (segs[-1].get("destination") or {}).get("iata_code") or ""
        dep = _fmt_time(segs[0].get("departing_at"))
        arr = _fmt_time(segs[-1].get("arriving_at"))
        if dep and arr:
            legs.append(f"{a}→{b} {dep} → {arr}".strip())
        else:
            legs.append(f"{a}→{b}".strip("→"))
    return " | ".join(x for x in legs if x)


# -----------------------------
# Helpers (offer passengers)
# -----------------------------
def _fetch_offer_passengers(offer_id: str) -> List[Dict[str, Any]]:
    """Return [{'id': 'off_pax_...', 'type': 'adult'}, ...] for a given offer."""
    if not _DUFFEL_TOKEN or not offer_id:
        return []
    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(f"{_DUFFEL_BASE}/air/offers/{offer_id}", headers=_headers())
        if r.status_code >= 400:
            return []
        d = (r.json() or {}).get("data") or {}
        src = d.get("passengers") or d.get("offer_passengers") or []
        res: List[Dict[str, Any]] = []
        for p in src:
            if not isinstance(p, dict):
                continue
            _id = p.get("id")
            if _id:
                res.append({"id": _id, "type": (p.get("type") or "adult")})
        return res
    except Exception:
        return []


# -----------------------------
# Tools
# -----------------------------
@_tool
def duffel_search_offers(
    slices: List[Dict[str, str]],
    passengers: List[Dict[str, str]],
    cabin_class: Optional[str] = None,
    max_connections: Optional[int] = None,
    preferred_airlines: Optional[List[str]] = None,
    page: int = 1,
    page_size: int = 5,
) -> Dict[str, Any]:
    """
    Search flight offers (Duffel /air/offer_requests), return a paginated list.
    Returns each offer summary with native amount/currency, itinerary, and ≈USDC/FET conversions.
    """
    if not _DUFFEL_TOKEN:
        return {"error": "DUFFEL_TOKEN not set", "code": "NO_TOKEN"}

    body: Dict[str, Any] = {"slices": slices, "passengers": passengers}
    if cabin_class:
        body["cabin_class"] = cabin_class
    if max_connections is not None:
        body["max_connections"] = max_connections
    if preferred_airlines:
        body["allowed_carriers"] = preferred_airlines

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.post(f"{_DUFFEL_BASE}/air/offer_requests", headers=_headers(), json={"data": body})
        if r.status_code >= 400:
            return {"error": f"Duffel {r.status_code}: {r.text[:300]}", "code": "HTTP_ERROR"}

        data = r.json() or {}
        raw_offers = (data.get("data") or {}).get("offers") or []

        offers: List[Dict[str, Any]] = []
        for o in raw_offers:
            owner = o.get("owner") or {}
            airline = owner.get("name") or owner.get("iata_code") or ""
            total_amount = o.get("total_amount")
            total_currency = o.get("total_currency")
            itinerary = _format_itinerary(o.get("slices") or [])
            summary = {
                "id": o.get("id"),
                "airline": airline or "-",
                "total_amount": total_amount,
                "total_currency": total_currency,
                "itinerary": itinerary or "-",
            }
            offers.append(_apply_conversions(summary))

        # Sort
        def _sort_key(x: Dict[str, Any]) -> float:
            if "total_amount_usdc" in x:
                return float(x["total_amount_usdc"])
            try:
                return float(x.get("total_amount") or "1e18")
            except Exception:
                return 1e18

        offers.sort(key=_sort_key)

        # Pagination
        page_size = max(1, min(10, int(page_size)))
        page = max(1, int(page))
        count = len(offers)
        page_total = (count + page_size - 1) // page_size
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "offers": offers[start:end],
            "page": page,
            "page_total": page_total,
            "count": count,
        }

    except Exception as e:
        return {"error": f"duffel_search_offers failed: {type(e).__name__}: {e}", "code": "UNKNOWN"}


@_tool
def duffel_get_offer_with_services(offer_id: str) -> Dict[str, Any]:
    """
    Refresh an offer (price + bags) and apply conversions.
    ALSO returns 'offer_passengers': [{'id': 'off_pax_...', 'type': 'adult'|'child'|'infant'}, ...]
    """
    if not _DUFFEL_TOKEN:
        return {"error": "DUFFEL_TOKEN not set", "code": "NO_TOKEN"}

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.get(
                f"{_DUFFEL_BASE}/air/offers/{offer_id}",
                headers=_headers(),
                params={"return_available_services": "true"},
            )
        if r.status_code >= 400:
            return {"error": f"Duffel {r.status_code}: {r.text[:300]}", "code": "HTTP_ERROR"}

        d = (r.json() or {}).get("data") or {}
        owner = d.get("owner") or {}
        airline = owner.get("name") or owner.get("iata_code") or ""

        # offer_passengers
        offer_pax = d.get("passengers") or d.get("offer_passengers") or []
        offer_passengers: List[Dict[str, Any]] = []
        for p in offer_pax:
            if isinstance(p, dict) and p.get("id"):
                offer_passengers.append({"id": p.get("id"), "type": (p.get("type") or "adult")})

        res: Dict[str, Any] = {
            "id": d.get("id"),
            "airline": airline or "-",
            "total_amount": d.get("total_amount"),
            "total_currency": d.get("total_currency"),
            "itinerary": _format_itinerary(d.get("slices") or []),
            "payment_required_by": (d.get("payment_requirements") or {}).get("payment_required_by"),
            "bags": [],
            "offer_passengers": offer_passengers,
        }
        for svc in (d.get("available_services") or []):
            if not isinstance(svc, dict):
                continue
            bag = {
                "id": svc.get("id"),
                "name": (svc.get("name") or (svc.get("metadata") or {}).get("name") or "Bag"),
                "total_amount": svc.get("total_amount"),
                "total_currency": svc.get("total_currency"),
            }
            res["bags"].append(_apply_conversions(bag))

        res = _apply_conversions(res)
        return res

    except Exception as e:
        return {"error": f"offer_refresh_failed: {type(e).__name__}: {e}", "code": "UNKNOWN"}


def _sanitize_passengers(passengers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in passengers or []:
        if not isinstance(p, dict):
            continue
        pp: Dict[str, Any] = {
            "type": p.get("type") or "adult",
            "given_name": p.get("given_name") or p.get("first_name") or p.get("givenName"),
            "family_name": p.get("family_name") or p.get("last_name") or p.get("familyName"),
            "born_on": p.get("born_on") or p.get("dob") or p.get("date_of_birth"),
        }
        if p.get("gender"):
            pp["gender"] = p["gender"]
        if p.get("title"):
            pp["title"] = p["title"]
        if p.get("email"):
            pp["email"] = p["email"]
        if p.get("phone_number"):
            pp["phone_number"] = p["phone_number"]
        if p.get("id"):
            pp["id"] = p["id"]
        out.append(pp)
    return out


def _summarize_order_email(d: Dict[str, Any]) -> str:
    total = d.get("total_amount")
    cur = d.get("total_currency")
    br = d.get("booking_reference") or (d.get("booking_references") or [{}])[0].get("booking_reference")
    airline = (d.get("owner") or {}).get("name") or (d.get("owner") or {}).get("iata_code") or ""
    itin = _format_itinerary(d.get("slices") or [])
    lines = [
        "Your booking is confirmed ✅",
        f"Airline: {airline or '-'}",
        f"Itinerary: {itinerary or '-'}",
        f"Booking reference: {br or '-'}",
        f"Total: {total or '-'} {cur or ''}".strip(),
        "",
        "Thank you for booking with Innovation Lab Flights.",
    ]
    return "\n".join(lines)


@_tool
def duffel_create_order(
    offer_id: str,
    passengers: List[Dict[str, Any]],
    services: Optional[List[Dict[str, Any]]] = None,
    pay_with_balance_now: bool = False,
    notify_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an order.
    - Default: HOLD (no payments in this call).
    - If pay_with_balance_now=True, we add a balance payment for the offer total.
    - We auto-attach offer_passenger IDs (1:1 by order) if missing in submitted passengers.
    """
    if not _DUFFEL_TOKEN:
        return {"error": "DUFFEL_TOKEN not set", "code": "NO_TOKEN"}

    pax = _sanitize_passengers(passengers)

    # Ensure offer_passenger IDs are attached
    if not all(p.get("id") for p in pax):
        off_pax = _fetch_offer_passengers(offer_id)
        for i, p in enumerate(pax):
            if i < len(off_pax) and not p.get("id"):
                p["id"] = off_pax[i]["id"]

    body: Dict[str, Any] = {"selected_offers": [offer_id], "passengers": pax}
    if services:
        body["selected_services"] = services

    if pay_with_balance_now:
        # Inline payment = instant ticketing
        try:
            with httpx.Client(timeout=15) as client:
                r_get = client.get(f"{_DUFFEL_BASE}/air/offers/{offer_id}", headers=_headers())
            d = (r_get.json() or {}).get("data") or {} if r_get.status_code < 400 else {}
            amt = d.get("total_amount")
            cur = d.get("total_currency")
            if amt and cur:
                body["payments"] = [{"type": "balance", "amount": str(amt), "currency": str(cur)}]
        except Exception:
            pass

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            rr = client.post(f"{_DUFFEL_BASE}/air/orders", headers=_headers(), json={"data": body})
        if rr.status_code >= 400:
            return {"error": f"Duffel {rr.status_code}: {rr.text[:300]}", "code": "HTTP_ERROR"}

        data = (rr.json() or {}).get("data") or {}
        out = {
            "id": data.get("id"),
            "booking_reference": data.get("booking_reference") or (data.get("booking_references") or [{}])[0].get("booking_reference"),
            "total_amount": data.get("total_amount"),
            "total_currency": data.get("total_currency"),
            "awaiting_payment": bool((data.get("payment_status") or {}).get("awaiting_payment")),
        }

        if notify_email and _smtp_enabled():
            try:
                with httpx.Client(timeout=15) as client:
                    r_full = client.get(f"{_DUFFEL_BASE}/air/orders/{out['id']}", headers=_headers())
                full = (r_full.json() or {}).get("data") or data
                _send_email(notify_email, "Your flight booking", _summarize_order_email(full))
            except Exception:
                pass

        return out
    except Exception as e:
        return {"error": f"order_failed: {type(e).__name__}: {e}", "code": "UNKNOWN"}


@_tool
def duffel_pay_hold_order(order_id: str, amount: str, currency: str) -> Dict[str, Any]:
    """Pay a HOLD order using seller balance (POST /air/payments)."""
    if not _DUFFEL_TOKEN:
        return {"error": "DUFFEL_TOKEN not set", "code": "NO_TOKEN"}
    payload = {"data": {"order_id": order_id, "type": "balance", "amount": str(amount), "currency": str(currency)}}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.post(f"{_DUFFEL_BASE}/air/payments", headers=_headers(), json=payload)
        if r.status_code >= 400:
            return {"error": f"Duffel {r.status_code}: {r.text[:300]}", "code": "HTTP_ERROR"}
        return {"ok": True}
    except Exception as e:
        return {"error": f"pay_hold_failed: {type(e).__name__}: {e}", "code": "UNKNOWN"}


@_tool
def duffel_get_order(order_id: str) -> Dict[str, Any]:
    """Fetch an order summary."""
    if not _DUFFEL_TOKEN:
        return {"error": "DUFFEL_TOKEN not set", "code": "NO_TOKEN"}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.get(f"{_DUFFEL_BASE}/air/orders/{order_id}", headers=_headers())
        if r.status_code >= 400:
            return {"error": f"Duffel {r.status_code}: {r.text[:300]}", "code": "HTTP_ERROR"}
        d = (r.json() or {}).get("data") or {}
        return {
            "id": d.get("id"),
            "booking_reference": d.get("booking_reference") or (d.get("booking_references") or [{}])[0].get("booking_reference"),
            "total_amount": d.get("total_amount"),
            "total_currency": d.get("total_currency"),
            "payment_status": d.get("payment_status"),
            "cancellation": d.get("cancellation"),
            "available_actions": d.get("available_actions"),
        }
    except Exception as e:
        return {"error": f"get_order_failed: {type(e).__name__}: {e}", "code": "UNKNOWN"}


@_tool
def duffel_create_order_cancellation(order_id: str) -> Dict[str, Any]:
    """Create a cancellation request to preview refunds before confirmation."""
    if not _DUFFEL_TOKEN:
        return {"error": "DUFFEL_TOKEN not set", "code": "NO_TOKEN"}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.post(f"{_DUFFEL_BASE}/air/order_cancellations", headers=_headers(), json={"data": {"order_id": order_id}})
        if r.status_code >= 400:
            return {"error": f"Duffel {r.status_code}: {r.text[:300]}", "code": "HTTP_ERROR"}
        d = (r.json() or {}).get("data") or {}
        return {
            "id": d.get("id"),
            "refund_amount": d.get("refund_amount"),
            "refund_currency": d.get("refund_currency"),
            "refund_to": d.get("refund_to"),
            "expires_at": d.get("expires_at"),
            "status": d.get("status"),
        }
    except Exception as e:
        return {"error": f"create_cxl_failed: {type(e).__name__}: {e}", "code": "UNKNOWN"}


@_tool
def duffel_confirm_order_cancellation(order_cancellation_id: str, notify_email: Optional[str] = None) -> Dict[str, Any]:
    """Confirm a previously created cancellation."""
    if not _DUFFEL_TOKEN:
        return {"error": "DUFFEL_TOKEN not set", "code": "NO_TOKEN"}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.post(
                f"{_DUFFEL_BASE}/air/order_cancellations/{order_cancellation_id}/actions/confirm",
                headers=_headers(),
                json={"data": {}},
            )
        if r.status_code >= 400:
            return {"error": f"Duffel {r.status_code}: {r.text[:300]}", "code": "HTTP_ERROR"}

        if notify_email and _smtp_enabled():
            try:
                _send_email(
                    notify_email,
                    "Your booking was cancelled",
                    "Your cancellation has been confirmed. Refund details will follow per airline policy.",
                )
            except Exception:
                pass

        return {"ok": True}
    except Exception as e:
        return {"error": f"confirm_cxl_failed: {type(e).__name__}: {e}", "code": "UNKNOWN"}


# Export tools
@_tool
def list_orders() -> Dict[str, Any]:
    """
    List all orders stored in the session (stored by payment_proto after successful booking).
    Returns a list of orders with their details.
    Note: This is a placeholder - actual implementation will read from agent storage in chat_proto.
    """
    return {
        "message": "list_orders called - implementation handled by chat_proto",
        "orders": []
    }

@_tool
def get_order_cancellation_quote(order_id: str) -> Dict[str, Any]:
    """
    Get a cancellation quote for an order.
    Calls Duffel API to create an order_cancellation and returns refund details.
    """
    token = os.getenv("DUFFEL_TOKEN")
    if not token:
        return {"error": "DUFFEL_TOKEN not set", "code": "NO_TOKEN"}
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v2",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    try:
        # First check if order is cancellable
        with httpx.Client(timeout=20) as client:
            r = client.get(f"https://api.duffel.com/air/orders/{order_id}", headers=headers)
        
        if r.status_code >= 400:
            return {"error": f"Duffel {r.status_code}: {r.text[:300]}", "code": "HTTP_ERROR"}
        
        order_data = (r.json() or {}).get("data") or {}
        available_actions = order_data.get("available_actions") or []
        
        if "cancel" not in available_actions:
            return {"error": "This order is not cancellable", "code": "NOT_CANCELLABLE"}
        
        # Create cancellation quote
        with httpx.Client(timeout=20) as client:
            cr = client.post(
                "https://api.duffel.com/air/order_cancellations",
                headers=headers,
                json={"data": {"order_id": order_id}}
            )
        
        if cr.status_code >= 400:
            return {"error": f"Duffel {cr.status_code}: {cr.text[:300]}", "code": "HTTP_ERROR"}
        
        cancellation_data = (cr.json() or {}).get("data") or {}
        
        return {
            "order_cancellation_id": cancellation_data.get("id"),
            "order_id": order_id,
            "refund_amount": cancellation_data.get("refund_amount"),
            "refund_currency": cancellation_data.get("refund_currency"),
            "refund_to": cancellation_data.get("refund_to"),
            "expires_at": cancellation_data.get("expires_at"),
        }
    
    except Exception as e:
        return {"error": f"get_order_cancellation_quote failed: {type(e).__name__}: {e}", "code": "UNKNOWN"}

@_tool
def confirm_order_cancellation(order_cancellation_id: str) -> Dict[str, Any]:
    """
    Confirm and execute an order cancellation.
    """
    token = os.getenv("DUFFEL_TOKEN")
    if not token:
        return {"error": "DUFFEL_TOKEN not set", "code": "NO_TOKEN"}
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v2",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    try:
        with httpx.Client(timeout=20) as client:
            r = client.post(
                f"https://api.duffel.com/air/order_cancellations/{order_cancellation_id}/actions/confirm",
                headers=headers
            )
        
        if r.status_code >= 400:
            return {"error": f"Duffel {r.status_code}: {r.text[:300]}", "code": "HTTP_ERROR"}
        
        cancellation_data = (r.json() or {}).get("data") or {}
        
        return {
            "order_cancellation_id": cancellation_data.get("id"),
            "order_id": cancellation_data.get("order_id"),
            "refund_amount": cancellation_data.get("refund_amount"),
            "refund_currency": cancellation_data.get("refund_currency"),
            "confirmed_at": cancellation_data.get("confirmed_at"),
        }
    
    except Exception as e:
        return {"error": f"confirm_order_cancellation failed: {type(e).__name__}: {e}", "code": "UNKNOWN"}

try:
    TOOLS = [
        duffel_search_offers,
        duffel_get_offer_with_services,
        duffel_create_order,
        duffel_pay_hold_order,
        duffel_get_order,
        duffel_create_order_cancellation,
        duffel_confirm_order_cancellation,
        list_orders,
        get_order_cancellation_quote,
        confirm_order_cancellation,
    ]
except Exception:  # pragma: no cover
    TOOLS = []

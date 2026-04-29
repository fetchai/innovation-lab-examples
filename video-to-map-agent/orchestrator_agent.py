import asyncio
import base64
import os
import json
import re
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote, urlencode
from uuid import UUID, uuid4
from dotenv import load_dotenv
from openai import OpenAI
import requests

try:
    import stripe as _stripe_lib  # type: ignore
except Exception:  # pragma: no cover — stripe is optional (dev mode)
    _stripe_lib = None  # type: ignore[assignment]

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    Resource,
    ResourceContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)
from uagents_core.storage import ExternalStorage
from shared_models import (
    TranscriptRequest,
    TranscriptResponse,
    LocationExtractionRequest,
    LocationExtractionResponse,
    AggregateRequest,
    AggregateResponse,
    TripPlannerRequest,
    TripPlannerResponse,
    WeatherMonitorRequest,
    WeatherSnapshotRequest,
    WeatherSnapshotResponse,
    PDFRequest,
    PDFResponse,
    ExcelRequest,
    ExcelResponse,
)

load_dotenv()

TRANSCRIPT_AGENT_ADDR = os.getenv("TRANSCRIPT_AGENT_ADDR")
LOCATION_AGENT_ADDR = os.getenv("LOCATION_AGENT_ADDR")
AGGREGATOR_AGENT_ADDR = os.getenv("AGGREGATOR_AGENT_ADDR")
TRIP_PLANNER_AGENT_ADDR = os.getenv("TRIP_PLANNER_AGENT_ADDR")
WEATHER_AGENT_ADDR = os.getenv("WEATHER_AGENT_ADDR")
PDF_AGENT_ADDR = os.getenv("PDF_AGENT_ADDR")
EXCEL_AGENT_ADDR = os.getenv("EXCEL_AGENT_ADDR")

# Cap per the product spec — the user can paste 1-4 URLs in a single chat.
_MAX_URLS_PER_REQUEST = 4

_ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8010"))

# pdf-podcast-agent / appliance-auto-whisperer pattern:
#   * mailbox  = Agentverse API key string  → ASI:One delivers chat via mailbox
#   * endpoint = direct submit URL          → mailbox is disabled, direct HTTP
# The two are mutually exclusive — passing both makes uAgents log
# "Endpoint configuration overrides mailbox setting" and silently drop chat.
_ORCHESTRATOR_ENDPOINT = os.getenv("ORCHESTRATOR_ENDPOINT", "").strip()
_AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY", "").strip()
_USE_MAILBOX = bool(_AGENTVERSE_API_KEY) and not _ORCHESTRATOR_ENDPOINT

# Agentverse ExternalStorage — kept as an optional secondary channel; the
# primary download mechanism is now the local file server below (matching
# the pdf-podcast-agent pattern, which ASI:One's chat UI renders reliably
# as clickable markdown links).
_AGENTVERSE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai").rstrip("/")
_STORAGE_URL = f"{_AGENTVERSE_URL}/v1/storage"
_ASSET_LIFETIME_HOURS = max(1, min(24, int(os.getenv("ASSET_LIFETIME_HOURS", "24"))))

# ── Local file server (clickable downloads) ─────────────────────────────────
# We serve the output/ directory over HTTP so that generated PDF / Excel /
# map PNGs come back as clickable markdown URLs in the chat — this is the
# exact pattern used by pdf-podcast-agent, which ASI:One renders reliably.
# The user clicks a URL in chat → browser opens http://localhost:PORT/file
# and downloads/views it.  Works out of the box as long as the user is
# testing on the same machine running the orchestrator.
_OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
_FILES_SERVER_PORT = int(os.getenv("FILES_SERVER_PORT", "8090"))
_FILES_SERVER_HOST = os.getenv("FILES_SERVER_HOST", "localhost")
# If the user exposes the output folder on a public URL (tunnel / reverse
# proxy / hosted), they can set FILES_PUBLIC_BASE to that URL and we'll
# use it instead of the localhost URL (e.g. https://trips.mydomain.com).
_FILES_PUBLIC_BASE = os.getenv("FILES_PUBLIC_BASE", "").rstrip("/")


def _start_files_server() -> None:
    """Background thread serving OUTPUT_DIR so download URLs are clickable."""
    try:
        handler = partial(SimpleHTTPRequestHandler, directory=str(_OUTPUT_DIR))
        server = HTTPServer(("0.0.0.0", _FILES_SERVER_PORT), handler)
        server.serve_forever()
    except OSError as e:  # port already in use — non-fatal
        print(f"[Files] could not start HTTP server on " f"{_FILES_SERVER_PORT}: {e}")


threading.Thread(
    target=_start_files_server,
    daemon=True,
    name="files-server",
).start()


def _file_url(file_path: str | None) -> str | None:
    """Return a URL the chat UI can render as a clickable download link.

    `file_path` can be an absolute path or a path relative to OUTPUT_DIR.
    Returns None if the file doesn't exist so callers can skip the link.
    """
    if not file_path:
        return None
    p = Path(file_path)
    if not p.is_absolute():
        p = _OUTPUT_DIR / p
    if not p.exists():
        return None
    name = quote(p.name)
    if _FILES_PUBLIC_BASE:
        return f"{_FILES_PUBLIC_BASE}/{name}"
    return f"http://{_FILES_SERVER_HOST}:{_FILES_SERVER_PORT}/{name}"


# Google Static Maps API — used to render a PNG preview of the curated
# driving route that we attach to the final chat response. The user sees
# the visual route inline and can click the accompanying "Open in Google
# Maps" link to launch the fully interactive JavaScript map.
_GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
_STATIC_MAP_SIZE = os.getenv("STATIC_MAP_SIZE", "640x400")
_STATIC_MAP_SCALE = os.getenv("STATIC_MAP_SCALE", "2")  # 2 = retina/HiDPI
_STATIC_MAP_MAXLBL = 9  # Google caps numeric labels at 1..9 per marker

_agent_kwargs: dict = dict(
    name="travel_map_orchestrator",
    seed=os.getenv("ORCHESTRATOR_SEED"),
    port=_ORCHESTRATOR_PORT,
    network="testnet",
    publish_agent_details=True,
)
if _USE_MAILBOX:
    _agent_kwargs["mailbox"] = _AGENTVERSE_API_KEY
else:
    _agent_kwargs["endpoint"] = [
        _ORCHESTRATOR_ENDPOINT or f"http://127.0.0.1:{_ORCHESTRATOR_PORT}/submit"
    ]

agent = Agent(**_agent_kwargs)


@agent.on_event("startup")
async def _log_routing_mode(ctx: Context) -> None:
    mode = "mailbox (Agentverse)" if _USE_MAILBOX else "direct HTTP endpoint"
    ctx.logger.info(f"[Orchestrator] routing mode: {mode}")
    if not _USE_MAILBOX and not _AGENTVERSE_API_KEY:
        ctx.logger.warning(
            "AGENTVERSE_API_KEY is not set — ASI:One chat cannot reach this "
            "agent via mailbox. Add AGENTVERSE_API_KEY to .env "
            "(https://innovationlab.fetch.ai/resources/docs/agentverse/agentverse-api-key)."
        )
    ctx.logger.info(
        f"[Orchestrator] sub-agents:\n"
        f"  transcript         {TRANSCRIPT_AGENT_ADDR or '(not set)'}\n"
        f"  location           {LOCATION_AGENT_ADDR or '(not set)'}\n"
        f"  aggregator         {AGGREGATOR_AGENT_ADDR or '(not set)'}\n"
        f"  trip planner       {TRIP_PLANNER_AGENT_ADDR or '(not set)'}\n"
        f"  weather            {WEATHER_AGENT_ADDR or '(not set)'}\n"
        f"  pdf                {PDF_AGENT_ADDR or '(not set)'}\n"
        f"  excel              {EXCEL_AGENT_ADDR or '(not set)'}"
    )
    base = _FILES_PUBLIC_BASE or (f"http://{_FILES_SERVER_HOST}:{_FILES_SERVER_PORT}")
    ctx.logger.info(
        f"[Files] serving output/ on {base} "
        f"(PDF + Excel + map PNG become clickable markdown links in chat)"
    )
    if _stripe_enabled():
        ctx.logger.info(
            f"[Orchestrator] Stripe paywall ACTIVE: {_price_display()} per "
            f"trip plan (test-mode key={_STRIPE_SECRET_KEY[:12]}...)"
        )
    else:
        ctx.logger.info(
            "[Orchestrator] Stripe paywall DISABLED (STRIPE_SECRET_KEY not "
            "set). Pipeline runs free of charge."
        )


asi1_client = OpenAI(
    base_url="https://api.asi1.ai/v1",
    api_key=os.getenv("ASI1_API_KEY"),
)

chat_proto = Protocol(spec=chat_protocol_spec)


# ── Stripe payment gate (SaaS trip-plan paywall) ──────────────────────────────
# Mirrors the pdf-podcast-agent + stripe-horoscope-agent pattern:
#   1. User sends a chat with YouTube URLs + preferences.
#   2. Orchestrator parses intent, creates an embedded Stripe Checkout Session,
#      persists the parsed intent under a per-sender "pending" state key,
#      and replies with `RequestPayment` whose metadata["stripe"] lets
#      ASI:One render the Stripe overlay inline in the chat.
#   3. User pays. ASI:One posts `CommitPayment(transaction_id=<session_id>)`.
#   4. Orchestrator verifies via Stripe API, sends `CompletePayment`, then
#      releases the saved pending state into the real pipeline.
# If STRIPE_SECRET_KEY is unset the gate is a no-op and the pipeline runs
# immediately on every chat message (free/dev mode).
_STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
_STRIPE_PUBLISHABLE = os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
_STRIPE_PRICE_CENTS = int(os.getenv("STRIPE_PRICE_CENTS", "299"))
_STRIPE_CURRENCY = (os.getenv("STRIPE_CURRENCY", "usd") or "usd").strip().lower()
_STRIPE_PRODUCT_NAME = (
    os.getenv("STRIPE_PRODUCT_NAME", "Travel Map Agent - Trip Plan") or ""
).strip() or "Travel Map Agent - Trip Plan"
_STRIPE_SUCCESS_URL = (
    os.getenv("STRIPE_SUCCESS_URL", "https://asi1.ai") or "https://asi1.ai"
).strip()
_STRIPE_CHECKOUT_EXPIRES_S = max(
    1800, min(24 * 60 * 60, int(os.getenv("STRIPE_CHECKOUT_EXPIRES_SECONDS", "1800")))
)
# Pending-payment state lives in `ctx.storage` under this key-prefix so
# multiple users in parallel don't collide. Entries expire after
# STRIPE_CHECKOUT_EXPIRES_SECONDS (matches the Stripe checkout TTL).
_PENDING_KEY_PREFIX = "travel_pending_payment:"


def _stripe_enabled() -> bool:
    return bool(_stripe_lib and _STRIPE_SECRET_KEY)


def _price_display() -> str:
    dollars = _STRIPE_PRICE_CENTS / 100
    return f"${dollars:.2f}"


def _create_embedded_checkout(
    *,
    user_address: str,
    chat_session_id: str,
    description: str,
) -> dict:
    """Create a Stripe embedded Checkout Session and return the payload
    that goes into ``RequestPayment.metadata["stripe"]``.

    Current Stripe API requires ``ui_mode="embedded_page"`` (the older
    ``"embedded"`` is now rejected).  ASI:One's chat UI also renders
    this value as an inline Stripe overlay — same convention used by
    the reference pdf-podcast-agent.
    """
    assert _stripe_lib is not None
    _stripe_lib.api_key = _STRIPE_SECRET_KEY  # type: ignore[union-attr]
    expires_at = int(time.time()) + _STRIPE_CHECKOUT_EXPIRES_S
    return_url = (
        f"{_STRIPE_SUCCESS_URL}"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
        f"&chat_session_id={chat_session_id}"
        f"&user={user_address}"
    )
    session = _stripe_lib.checkout.Session.create(  # type: ignore[union-attr]
        ui_mode="embedded_page",
        redirect_on_completion="if_required",
        mode="payment",
        payment_method_types=["card"],
        return_url=return_url,
        expires_at=expires_at,
        line_items=[
            {
                "price_data": {
                    "currency": _STRIPE_CURRENCY,
                    "unit_amount": _STRIPE_PRICE_CENTS,
                    "product_data": {
                        "name": _STRIPE_PRODUCT_NAME,
                        "description": description[:500],
                    },
                },
                "quantity": 1,
            }
        ],
        metadata={
            "user_address": user_address,
            "chat_session_id": chat_session_id,
            "service": "travel_map_agent",
        },
    )
    return {
        "client_secret": session.client_secret,
        "checkout_session_id": session.id,
        # Some ASI:One client versions look for `id`, others for
        # `checkout_session_id` — send both so the UI always finds it.
        "id": session.id,
        "publishable_key": _STRIPE_PUBLISHABLE,
        "currency": _STRIPE_CURRENCY,
        "amount_cents": _STRIPE_PRICE_CENTS,
        "ui_mode": "embedded_page",
    }


def _verify_checkout_session_paid(checkout_session_id: str) -> bool:
    """Confirm with Stripe that a Checkout Session has been paid."""
    assert _stripe_lib is not None
    _stripe_lib.api_key = _STRIPE_SECRET_KEY  # type: ignore[union-attr]
    session = _stripe_lib.checkout.Session.retrieve(checkout_session_id)  # type: ignore[union-attr]
    return getattr(session, "payment_status", None) == "paid"


def _pending_key(sender: str) -> str:
    return f"{_PENDING_KEY_PREFIX}{sender}"


def _load_pending(ctx: Context, sender: str) -> dict:
    raw = ctx.storage.get(_pending_key(sender))
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    # Drop stale entries so a user who abandons checkout can start over cleanly.
    try:
        exp = float(data.get("expires_at") or 0)
        if exp and time.time() > exp:
            return {}
    except Exception:
        return {}
    return data


def _save_pending(ctx: Context, sender: str, state: dict) -> None:
    ctx.storage.set(_pending_key(sender), json.dumps(state))


def _clear_pending(ctx: Context, sender: str) -> None:
    ctx.storage.set(_pending_key(sender), "")


# ── helpers ───────────────────────────────────────────────────────────────────


def extract_text(msg: ChatMessage) -> str:
    return " ".join(
        item.text for item in msg.content if isinstance(item, TextContent)
    ).strip()


_YOUTUBE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?"
    r"(?:youtube\.com/watch\?[^\s]*v=[\w\-]+|youtu\.be/[\w\-]+)"
    r"[\w\-/\?=&%\.]*",
    re.IGNORECASE,
)


def _extract_youtube_urls(text: str) -> list:
    """Find every YouTube URL in *text*, dedupe by video id, cap at the
    per-request limit. Always returns full https:// URLs."""
    raw_matches = _YOUTUBE_URL_RE.findall(text or "")
    seen_ids: set = set()
    urls: list = []
    for m in raw_matches:
        m = m.rstrip(".,;:)]>")
        if not m.startswith("http"):
            m = "https://" + m
        # Pull out the video id so https://youtu.be/X and
        # https://youtube.com/watch?v=X collapse into one entry.
        vid_match = re.search(r"(?:v=|youtu\.be/)([\w\-]{6,})", m)
        vid = vid_match.group(1) if vid_match else m
        if vid in seen_ids:
            continue
        seen_ids.add(vid)
        urls.append(m)
        if len(urls) >= _MAX_URLS_PER_REQUEST:
            break
    return urls


def _coerce_money(v) -> float:
    """ASI1 sometimes returns '$120' or '120.0' or None. Normalise to float."""
    if v is None:
        return 0.0
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(v))
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0


def parse_user_input(user_text: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    default_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    # URLs are deterministic — pull them with regex, don't trust ASI1.
    urls = _extract_youtube_urls(user_text)

    try:
        resp = asi1_client.chat.completions.create(
            model="asi1-mini",
            max_tokens=300,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract structured travel planning data from a message. "
                        "Return ONLY valid JSON. No markdown, no explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f'Extract from: "{user_text}"\n'
                        f"Today is {today}.\n\n"
                        "Return this exact JSON structure:\n"
                        "{\n"
                        f'  "trip_date": "YYYY-MM-DD (parse from message or default {default_date})",\n'
                        '  "trip_title": "short descriptive title or empty string",\n'
                        '  "preferences": "dietary/activity preferences as a short string or empty string",\n'
                        '  "budget_per_day": number — USD per person per day, or 0 if not mentioned,\n'
                        '  "total_budget": number — total USD across the whole trip, or 0 if not mentioned,\n'
                        '  "trip_days": integer — number of days, or 0 if not mentioned\n'
                        "}\n\n"
                        "Important: budget_per_day, total_budget, and trip_days "
                        "are all OPTIONAL. Return 0 for any the user did not "
                        "explicitly state. The agent figures out the rest."
                    ),
                },
            ],
        )
        raw = (
            resp.choices[0]
            .message.content.strip()
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )
        parsed = json.loads(raw)
    except Exception:
        parsed = {
            "trip_date": default_date,
            "trip_title": "Road Trip Itinerary",
            "preferences": "",
            "budget_per_day": 0.0,
            "total_budget": 0.0,
            "trip_days": 0,
        }

    parsed["youtube_urls"] = urls
    parsed["budget_per_day"] = _coerce_money(parsed.get("budget_per_day"))
    parsed["total_budget"] = _coerce_money(parsed.get("total_budget"))
    try:
        parsed["trip_days"] = max(0, int(float(parsed.get("trip_days", 0) or 0)))
    except Exception:
        parsed["trip_days"] = 0
    if not (parsed.get("trip_title") or "").strip():
        parsed["trip_title"] = "Road Trip Itinerary"
    if not (parsed.get("trip_date") or "").strip():
        parsed["trip_date"] = default_date

    return parsed


def _flatten_planned_stops(planned_days: list) -> list:
    """Return a flat list of stop dicts in the order they'll be driven."""
    return [stop for day in planned_days for stop in day.get("stops", [])]


def build_maps_url_from_planned(planned_days: list) -> str:
    """Build a Google Maps driving URL from only the curated planned stops.

    The geocoder's URL contains every raw validated stop (often 40+). Once
    the trip planner curates to a realistic set we rebuild a clean URL so
    the user gets a drivable route without the noise.
    """
    stops = _flatten_planned_stops(planned_days)
    if not stops:
        return ""
    if len(stops) == 1:
        only = stops[0]
        return (
            f"https://www.google.com/maps/search/?api=1"
            f"&query={quote(only.get('name', ''))}"
            f"&query_place_id={only.get('place_id', '')}"
        )
    origin = quote(stops[0].get("address", ""))
    destination = quote(stops[-1].get("address", ""))
    url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={origin}"
        f"&destination={destination}"
        f"&travelmode=driving"
    )
    # Google Maps accepts at most ~9 waypoints in a single URL; keep only
    # the middle stops and truncate if we somehow exceed that.
    middle = [quote(p.get("address", "")) for p in stops[1:-1]][:9]
    if middle:
        url += f"&waypoints={'|'.join(middle)}"
    return url


def _short_forecast(forecast: dict) -> str:
    """Compact one-liner summarising a per-stop forecast for inclusion in
    the plan outline we show ASI1 (and the plain-text fallback)."""
    if not forecast or not forecast.get("available"):
        return "forecast pending"
    cond = forecast.get("condition") or ""
    high = forecast.get("high_c")
    low = forecast.get("low_c")
    precip = forecast.get("precip_percent", 0) or 0
    parts = []
    if cond:
        parts.append(cond.lower())
    if high is not None and low is not None:
        parts.append(f"{high:.0f}/{low:.0f}C")
    if precip >= 30:
        parts.append(f"{precip}% rain")
    base = ", ".join(parts) if parts else "forecast available"
    if forecast.get("bad") and forecast.get("warning"):
        base += f" - WARNING: {forecast['warning']}"
    return base


def _format_consensus_block(planned_days: list, total_videos: int) -> str:
    """Top consensus stops across all source videos. Renders nothing if
    only a single video was used (frequency=1 everywhere)."""
    if total_videos <= 1:
        return ""
    flat = _flatten_planned_stops(planned_days)
    multi = [s for s in flat if int(s.get("frequency", 1)) >= 2]
    if not multi:
        return ""
    multi.sort(
        key=lambda s: (s.get("frequency", 0), s.get("rating", 0)),
        reverse=True,
    )
    lines: list[str] = []
    for s in multi[:5]:
        name = s.get("name", "")
        freq = int(s.get("frequency", 1))
        rating = float(s.get("rating", 0.0) or 0.0)
        rating_part = f" — {rating:.1f}★" if rating else ""
        lines.append(
            f"- **{name}** — mentioned in "
            f"{freq} of {total_videos} videos{rating_part}"
        )
    return "\n".join(lines)


def _inject_stop_photos(text: str, photo_urls: dict[str, str]) -> str:
    """Post-process the final Markdown to insert small inline thumbnails
    next to every stop bullet (consensus + day-by-day).

    Uses HTML ``<img>`` tags so the chat UI renders a compact thumbnail
    on the same line as the stop name rather than a full-width block image.
    Replaces ALL occurrences so both sections get photos.
    """
    if not photo_urls:
        return text
    for name, url in photo_urls.items():
        target = f"- **{name}**"
        replacement = (
            f'- <img src="{url}" width="64" height="48" ' f'alt="{name}"> **{name}**'
        )
        text = text.replace(target, replacement)
    return text


def format_final_response(
    planner_resp: TripPlannerResponse,
    pdf_filename: str,
    trip_date: str,
    preferences: str,
    video_summaries: list,
    snapshot_resp,  # Optional[WeatherSnapshotResponse]
    user_total_budget: float = 0.0,
) -> str:
    flat_stops = _flatten_planned_stops(planner_resp.days)

    # Build the source-line section: support 1..N videos.
    source_line = ""
    if video_summaries:
        if len(video_summaries) == 1:
            v = video_summaries[0]
            source_line = f"Video: {v.get('video_title', '')}"
            if v.get("channel_name"):
                source_line += f" by {v['channel_name']}"
        else:
            source_line = (
                f"Sources: {len(video_summaries)} travel vlogs - "
                + "; ".join(
                    f"\"{v.get('video_title', '?')}\""
                    + (f" by {v['channel_name']}" if v.get("channel_name") else "")
                    for v in video_summaries
                )
            )

    consensus_block = _format_consensus_block(
        planner_resp.days,
        len(video_summaries),
    )

    # Pull forecasts into a name-indexed dict for fast lookup.
    forecasts_by_name: dict = {}
    bad_stops: list = []
    if snapshot_resp and getattr(snapshot_resp, "success", False):
        for f in snapshot_resp.forecasts:
            forecasts_by_name[f.get("name", "")] = f
            if f.get("bad"):
                bad_stops.append(f)

    # Build a compact text outline of the plan (with weather) for ASI1.
    # NOTE: we only emit the weather bracket when forecasting succeeded,
    # so the LLM never hallucinates "forecast pending" for stops we don't
    # actually have data for.
    day_lines = []
    for day in planner_resp.days:
        day_lines.append(
            f"Day {day.get('day_number', '?')} - {day.get('theme', '')} "
            f"(~${day.get('estimated_cost_usd', 0):.0f})"
        )
        for s in day.get("stops", []):
            activity = s.get("activity", "") or "visit"
            fc = forecasts_by_name.get(s.get("name", ""))
            if fc and fc.get("available"):
                weather_part = f" [{_short_forecast(fc)}]"
            else:
                weather_part = ""
            day_lines.append(f"  - {s.get('name', '')}: {activity}{weather_part}")
    plan_text = "\n".join(day_lines)

    # Budget reconciliation summary (e.g. "fits your $200 budget").
    budget_blurb = ""
    assessment = (planner_resp.budget_assessment or "").lower()
    if assessment == "fits" and user_total_budget > 0:
        budget_blurb = (
            f"Total: ${planner_resp.total_estimated_cost:.0f} - "
            f"fits your ${user_total_budget:.0f} budget."
        )
    elif assessment == "tight":
        budget_blurb = (
            f"Total: ${planner_resp.total_estimated_cost:.0f} - "
            f"close to your budget; consider trimming a stop."
        )
    elif assessment == "over":
        budget_blurb = (
            f"Total: ${planner_resp.total_estimated_cost:.0f} - "
            f"over your budget. Consider removing a day or stop."
        )
    else:
        budget_blurb = f"Total estimated: ${planner_resp.total_estimated_cost:.0f}"

    try:
        resp = asi1_client.chat.completions.create(
            model="asi1-mini",
            max_tokens=800,
            temperature=0.6,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior travel concierge writing the "
                        "final chat message that hands a curated road-trip "
                        "plan back to the user. Your tone is warm but "
                        "crisp — like a human travel agent, not a chatbot.\n\n"
                        "RENDER THE OUTPUT IN MARKDOWN so the chat UI "
                        "displays clean headings, bold names, and bullets.\n\n"
                        "STRICT FORMAT RULES:\n"
                        "- First line must be an H2 title that names the "
                        "trip, e.g. '# Your California hiking adventure "
                        "is ready to go'.\n"
                        "- Use H2 ('## ...') for every section.\n"
                        "- Use H3 ('### Day 1 — <theme>  (~$<cost>)') for "
                        "each day of the plan.\n"
                        "- Under each day, use bullet lines in the form "
                        "'- **<stop name>** — <activity>[ [weather]]'.\n"
                        "- The vegetarian suggestion (if any) renders as a "
                        "bullet '- _Vegetarian-friendly_: <restaurant "
                        "name>[ (rating★)]'.\n"
                        "- Consensus stops render as bullets with bold "
                        "names and a star rating — copy the list verbatim "
                        "if provided.\n"
                        "- Separate every section with ONE blank line.\n"
                        "- No emojis.\n"
                        "- Never write 'forecast pending' or invent weather "
                        "for stops that didn't come with a forecast.\n"
                        "- Never mention PDF, Excel, map PNG, or Google "
                        "Maps URLs — the system appends those afterwards."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Compose the final handoff message using this "
                        "data.\n\n"
                        f"{source_line or 'Source: YouTube travel vlog'}\n"
                        f"Trip starts: {trip_date}\n"
                        f"User preferences: {preferences or 'not specified'}\n"
                        f"{budget_blurb}\n\n"
                        "Cross-video consensus block (markdown bullets — "
                        "reproduce verbatim when non-empty):\n"
                        f"{consensus_block or '(none)'}\n\n"
                        "Day-by-day plan (weather bracket already inline — "
                        "copy exactly when present, omit otherwise):\n"
                        f"{plan_text}\n\n"
                        "Initial weather scan flagged "
                        f"{len(bad_stops)} stop(s) with concerning "
                        "conditions: "
                        f"{', '.join(s.get('name', '') for s in bad_stops) or 'none'}.\n\n"
                        "Produce exactly these sections, in this order, "
                        "each separated by one blank line:\n\n"
                        "1. An H2 title: '## <warm, specific trip title>'.\n"
                        "2. One sentence (no heading) that warmly "
                        "summarises the trip.\n"
                        "3. If the consensus block is non-empty: an H2 "
                        "heading '## Stops that appeared in multiple "
                        "videos' followed by the consensus bullets, "
                        "verbatim. Otherwise skip this whole section.\n"
                        "4. An H2 heading '## Your day-by-day plan'. "
                        "Under it, for each day emit an H3 like "
                        "'### Day 1 — <theme>  (~$<cost>)' followed by "
                        "the stops as bullets '- **<stop>** — <activity>"
                        "[ [weather]]'. If the user's preferences mention "
                        "vegetarian/vegan, append a final bullet "
                        "'- _Vegetarian-friendly_: <first nearby veg "
                        "restaurant>[ (<rating>★)]' (skip that bullet if "
                        "no match is available).\n"
                        "5. An H2 heading '## Budget' followed by one "
                        f"short sentence incorporating: {budget_blurb}\n"
                        "6. An H2 heading '## Initial weather check'. "
                        "If any stops were flagged, list them as bullets "
                        "'- **<name>**: <warning>' and add the sentence "
                        "'Consider rescheduling or swapping these.' below. "
                        "Otherwise write the single sentence 'Conditions "
                        "look workable at every stop so far.'\n"
                        "7. One italic line: "
                        f"'_Weather agent will keep watching all stops "
                        f"daily until {trip_date}._'\n\n"
                        "Keep the whole message under 550 words. Emit "
                        "nothing else — no closing remarks, no signatures."
                    ),
                },
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # Deterministic markdown fallback — same layout as the LLM prompt.
        trip_title = "Your road trip is ready"
        if video_summaries:
            v = video_summaries[0]
            title = v.get("video_title") or ""
            if title:
                trip_title = f"Your road trip inspired by {title[:60]}"

        lines: list[str] = [f"# {trip_title}"]
        lines += [
            "",
            f"A curated {len(planner_resp.days)}-day plan with "
            f"{len(flat_stops)} stops, estimated at "
            f"${planner_resp.total_estimated_cost:.0f}.",
        ]
        if source_line:
            lines += ["", f"_{source_line}_"]
        if consensus_block:
            lines += [
                "",
                "## Stops that appeared in multiple videos",
                consensus_block,
            ]

        lines += ["", "## Your day-by-day plan"]
        for day in planner_resp.days:
            lines += [
                "",
                f"### Day {day.get('day_number', '?')} — "
                f"{day.get('theme', '')} "
                f"(~${day.get('estimated_cost_usd', 0):.0f})",
            ]
            for s in day.get("stops", []):
                fc = forecasts_by_name.get(s.get("name", ""))
                weather_tag = (
                    f" [{_short_forecast(fc)}]" if fc and fc.get("available") else ""
                )
                lines.append(
                    f"- **{s.get('name', '')}** — "
                    f"{s.get('activity', '') or 'visit'}{weather_tag}"
                )
            if preferences and "veg" in preferences.lower():
                for s in day.get("stops", []):
                    rests = s.get("nearby_restaurants") or []
                    if rests:
                        r = rests[0]
                        rating = r.get("rating")
                        rating_part = f" ({rating}★)" if rating else ""
                        lines.append(
                            f"- _Vegetarian-friendly_: "
                            f"{r.get('name', '')}{rating_part}"
                        )
                        break

        lines += ["", "## Budget", budget_blurb]
        lines += ["", "## Initial weather check"]
        if bad_stops:
            for f in bad_stops:
                lines.append(f"- **{f.get('name', '')}**: {f.get('warning', '')}")
            lines.append("")
            lines.append("Consider rescheduling or swapping these.")
        else:
            lines.append("Conditions look workable at every stop so far.")
        lines += [
            "",
            f"_Weather agent will keep watching all stops daily until "
            f"{trip_date}._",
        ]
        return "\n".join(lines)


async def send_status(ctx: Context, sender: str, text: str):
    """Mid-workflow status message — no EndSessionContent."""
    await ctx.send(
        sender,
        ChatMessage(
            msg_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            content=[TextContent(type="text", text=f"[ {text} ]")],
        ),
    )


def _upload_file_as_resource(
    ctx: Context,
    sender: str,
    filepath: str,
    filename: str,
    mime_type: str,
    role: str,
    extra_metadata: dict | None = None,
) -> ResourceContent | None:
    """Upload *filepath* to Agentverse ExternalStorage, grant *sender* read
    access, and return a ResourceContent that renders in ASI:One chat as a
    clickable download link. Returns None (and logs) on any failure — the
    caller should fall back to text-only output so the user still gets
    their itinerary even if the upload step blips.
    """
    if not _AGENTVERSE_API_KEY:
        ctx.logger.warning(
            "Skipping %s upload — AGENTVERSE_API_KEY not set, so files "
            "can't be attached. Add it to .env to enable clickable "
            "download links.",
            filename,
        )
        return None
    if not filepath or not os.path.isfile(filepath):
        ctx.logger.warning("Skipping upload — file missing: %s", filepath)
        return None
    try:
        with open(filepath, "rb") as fh:
            data = fh.read()
    except Exception as e:
        ctx.logger.error("Couldn't read %s for upload: %s", filepath, e)
        return None

    try:
        storage = ExternalStorage(
            api_token=_AGENTVERSE_API_KEY,
            storage_url=_STORAGE_URL,
        )
        asset_id = storage.create_asset(
            name=filename,
            content=data,
            mime_type=mime_type,
            lifetime_hours=_ASSET_LIFETIME_HOURS,
        )
        storage.set_permissions(
            asset_id=asset_id,
            agent_address=sender,
            read=True,
            write=False,
        )
    except Exception as e:
        ctx.logger.error("ExternalStorage upload failed for %s: %s", filename, e)
        return None

    ctx.logger.info(
        "Uploaded %s to Agentverse storage as asset_id=%s (%d bytes)",
        filename,
        asset_id,
        len(data),
    )
    metadata = {
        "mime_type": mime_type,
        "role": role,
        "filename": filename,
    }
    if extra_metadata:
        for k, v in extra_metadata.items():
            if v is None:
                continue
            metadata[str(k)] = str(v)
    return ResourceContent(
        resource_id=UUID(asset_id),
        resource=Resource(
            uri=f"agent-storage://{_STORAGE_URL}/{asset_id}",
            metadata=metadata,
        ),
    )


# ── Google Static Maps preview ────────────────────────────────────────────────


def _build_static_map_url(stops: list) -> str | None:
    """Build a Google Static Maps API URL rendering the curated route
    with numbered markers + a blue driving polyline connecting them.

    Returns None if we lack either an API key or enough lat/lng data to
    make a meaningful picture.
    """
    if not _GOOGLE_MAPS_API_KEY or not stops:
        return None
    pts: list = []
    for s in stops:
        try:
            lat = float(s.get("lat", 0) or 0)
            lng = float(s.get("lng", 0) or 0)
        except Exception:
            continue
        if lat or lng:
            pts.append((lat, lng))
    if not pts:
        return None

    params: list = [
        ("size", _STATIC_MAP_SIZE),
        ("scale", _STATIC_MAP_SCALE),
        ("maptype", "roadmap"),
    ]
    # Numbered markers for the first _STATIC_MAP_MAXLBL stops, plain red
    # dots after that so the image still fits in Google's URL-length cap.
    for idx, (lat, lng) in enumerate(pts, start=1):
        if idx <= _STATIC_MAP_MAXLBL:
            marker = f"color:red|label:{idx}|{lat:.6f},{lng:.6f}"
        else:
            marker = f"color:red|size:small|{lat:.6f},{lng:.6f}"
        params.append(("markers", marker))
    # Blue polyline in driving order.
    if len(pts) >= 2:
        path_pts = "|".join(f"{lat:.6f},{lng:.6f}" for lat, lng in pts)
        params.append(("path", f"color:0x0000ffff|weight:4|{path_pts}"))
    params.append(("key", _GOOGLE_MAPS_API_KEY))

    url = "https://maps.googleapis.com/maps/api/staticmap?" + urlencode(params)
    # Google caps static-map URLs at 16,384 chars; well under that even for
    # 50+ stops thanks to the path polyline being a single parameter.
    return url


def _fetch_static_map_png(ctx: Context, stops: list) -> bytes | None:
    """Download the Static Maps PNG for *stops*. Safe to call on the
    event loop only via run_in_executor — uses blocking requests."""
    url = _build_static_map_url(stops)
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=15)
    except Exception as exc:
        ctx.logger.warning(f"[Map] Static Maps fetch failed: {exc}")
        return None
    if resp.status_code != 200:
        ctx.logger.warning(
            f"[Map] Static Maps HTTP {resp.status_code}: "
            f"{resp.text[:200] if resp.content else ''}"
        )
        return None
    if not resp.content.startswith(b"\x89PNG"):
        # Google occasionally returns a 200 with an error image instead;
        # abort so we don't attach a "billing not enabled" graphic.
        ctx.logger.warning("[Map] Static Maps returned non-PNG payload")
        return None
    return resp.content


def _upload_static_map_as_resource(
    ctx: Context,
    sender: str,
    stops: list,
    interactive_maps_url: str,
) -> ResourceContent | None:
    """Fetch the Static Maps PNG, upload to Agentverse storage, and
    return a ResourceContent image pointing at it. The resource metadata
    carries the interactive Google Maps driving URL under multiple keys
    (link_url / click_url / target_uri) so that whichever convention the
    chat UI uses to make thumbnails clickable finds it."""
    png = _fetch_static_map_png(ctx, stops)
    if not png:
        return None
    import tempfile

    with tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
        prefix="trip_map_",
    ) as tmp:
        tmp.write(png)
        tmp_path = tmp.name
    try:
        return _upload_file_as_resource(
            ctx,
            sender,
            tmp_path,
            filename=f"trip_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            mime_type="image/png",
            role="trip-map-preview",
            extra_metadata={
                "link_url": interactive_maps_url,
                "click_url": interactive_maps_url,
                "target_uri": interactive_maps_url,
                "caption": "Open interactive Google Maps route",
            },
        )
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def _resolve_place_photo_url(photo_reference: str, max_width: int = 150) -> str | None:
    """Resolve a Google Places photo_reference to a public HTTPS CDN URL.

    The Places Photo API returns a 302 redirect chain ending at a
    ``lh3.googleusercontent.com`` URL.  We follow the redirects and
    return the final URL so it can be embedded directly in Markdown
    without exposing the API key.  Blocking — call via to_thread.
    """
    if not _GOOGLE_MAPS_API_KEY or not photo_reference:
        return None
    api_url = "https://maps.googleapis.com/maps/api/place/photo?" + urlencode(
        {
            "maxwidth": max_width,
            "photo_reference": photo_reference,
            "key": _GOOGLE_MAPS_API_KEY,
        }
    )
    try:
        resp = requests.head(api_url, allow_redirects=True, timeout=10)
        if resp.status_code == 200 and resp.url.startswith("https://"):
            return resp.url
    except Exception:
        pass
    return None


async def send_final(
    ctx: Context,
    sender: str,
    text: str,
    attachments: list | None = None,
):
    """Final response — always includes EndSessionContent.

    Any `ResourceContent` passed in *attachments* is rendered by the
    ASI:One chat UI as a clickable, downloadable file link alongside the
    text reply.
    """
    content: list = [TextContent(type="text", text=text)]
    for att in attachments or []:
        if att is not None:
            content.append(att)
    content.append(EndSessionContent(type="end-session"))
    await ctx.send(
        sender,
        ChatMessage(
            msg_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            content=content,
        ),
    )


# ── chat protocol handler ─────────────────────────────────────────────────────


@chat_proto.on_message(ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info("Chat ack from %s for msg_id=%s", sender, msg.acknowledged_msg_id)


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # rule 1 — ChatAcknowledgement MUST be first
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    # On the opening ChatMessage of a session the ASI:One UI expects
    # an early "attachments: true" metadata hint so it knows this agent
    # supports sending (and receiving) files. We reply with a no-op
    # MetadataContent the same way the Innovation Lab image agent does.
    if any(isinstance(c, StartSessionContent) for c in msg.content):
        await ctx.send(
            sender,
            ChatMessage(
                msg_id=uuid4(),
                timestamp=datetime.now(timezone.utc),
                content=[
                    MetadataContent(
                        type="metadata",
                        metadata={"attachments": "true"},
                    ),
                ],
            ),
        )

    user_text = extract_text(msg)
    ctx.logger.info(f"Received: {user_text}")
    if not user_text:
        # StartSession-only ping with no actual text — nothing to plan yet.
        return

    # step 1 — parse user input with ASI1 (URLs via deterministic regex)
    parsed = parse_user_input(user_text)
    youtube_urls = parsed.get("youtube_urls", []) or []

    # If we're mid-checkout for this user, decide whether the new message
    # is (a) a nudge/retry → resend the same RequestPayment, or (b) a fresh
    # plan request with new URLs → drop the pending payment and start over.
    pending = _load_pending(ctx, sender) if _stripe_enabled() else {}
    if pending and pending.get("checkout_session_id"):
        prior_urls = list(pending.get("parsed", {}).get("youtube_urls") or [])
        if youtube_urls and set(youtube_urls) != set(prior_urls):
            ctx.logger.info(
                "[Payment] user sent new URLs mid-checkout — dropping old pending state"
            )
            _clear_pending(ctx, sender)
            pending = {}
        else:
            await _resend_pending_payment(ctx, sender, pending)
            return

    if not youtube_urls:
        fee_note = (
            f"\n\nNote: generating a trip plan costs {_price_display()} "
            "(Stripe checkout appears in chat when you send your URLs)."
            if _stripe_enabled()
            else ""
        )
        await send_final(
            ctx,
            sender,
            "Hi! I'm the Travel Map Agent.\n\n"
            "Drop 1-4 YouTube travel vlog URLs in one message and I'll "
            "merge them into a single road trip - the more videos you give "
            "me, the more I can rank stops by what multiple creators agree "
            "on. I'll handle the days, the order, and the routing for you.\n\n"
            "Examples:\n"
            "  'Plan a trip from this video: https://youtu.be/VIDEO_ID. "
            "Vegetarian, $200 total.'\n"
            "  'Here are 3 California vlogs - https://youtu.be/A "
            "https://youtu.be/B https://youtu.be/C. Budget $400, "
            "love hiking.'"
            f"{fee_note}",
        )
        return

    # step 1.5 — Stripe payment gate (SaaS paywall for trip-plan generation)
    if _stripe_enabled():
        await _gate_with_payment(ctx, sender, parsed)
        return

    # No gate → run the pipeline directly (free/dev mode)
    await _run_travel_pipeline(ctx, sender, parsed)


async def _gate_with_payment(ctx: Context, sender: str, parsed: dict) -> None:
    """Create a Stripe embedded checkout, persist the parsed intent, and
    send a RequestPayment so ASI:One renders the payment form inline.

    The real pipeline only runs once `on_commit_payment` verifies the
    checkout and replays the saved intent.
    """
    urls = parsed.get("youtube_urls") or []
    description = (
        f"Curate a {_count_description(urls)} road trip from your "
        f"travel vlog{'s' if len(urls) != 1 else ''}. "
        "Includes a day-by-day plan, Google Maps route, PDF guide, Excel "
        "workbook, and daily weather monitoring until your trip date."
    )

    try:
        checkout = await asyncio.to_thread(
            _create_embedded_checkout,
            user_address=sender,
            chat_session_id=str(ctx.session),
            description=description,
        )
    except Exception as exc:
        ctx.logger.error(f"[Payment] Stripe checkout create failed: {exc}")
        await send_final(
            ctx,
            sender,
            "Payment service is temporarily unavailable. Please try again "
            f"in a minute. (Error: {exc})",
        )
        return

    _save_pending(
        ctx,
        sender,
        {
            "checkout_session_id": checkout["checkout_session_id"],
            "parsed": parsed,
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + _STRIPE_CHECKOUT_EXPIRES_S,
        },
    )

    await ctx.send(
        sender,
        RequestPayment(
            accepted_funds=[
                Funds(
                    currency=_STRIPE_CURRENCY.upper(),
                    amount=f"{_STRIPE_PRICE_CENTS / 100:.2f}",
                    payment_method="stripe",
                )
            ],
            recipient=str(ctx.agent.address),
            deadline_seconds=_STRIPE_CHECKOUT_EXPIRES_S,
            reference=str(ctx.session),
            description=(
                f"Pay {_price_display()} to generate your curated trip plan "
                f"from {len(urls)} video{'s' if len(urls) != 1 else ''}."
            ),
            metadata={"stripe": checkout, "service": "travel_map_agent"},
        ),
    )
    await ctx.send(
        sender,
        ChatMessage(
            msg_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"Your {_count_description(urls)} road trip plan costs "
                        f"{_price_display()}. Complete the Stripe checkout above to "
                        "release the workflow.\n\n"
                        "Once paid I'll fetch transcripts, merge locations across "
                        "videos, curate the best stops, plan day-by-day routing, "
                        "pull weather forecasts, and deliver a PDF + Excel guide "
                        "right here in chat."
                    ),
                )
            ],
        ),
    )
    ctx.logger.info(
        f"[Payment] RequestPayment sent "
        f"(checkout={checkout['checkout_session_id'][:20]}..., "
        f"{_STRIPE_PRICE_CENTS}c, {len(urls)} url(s))"
    )


async def _resend_pending_payment(ctx: Context, sender: str, pending: dict) -> None:
    """User sent another chat while their Stripe checkout is still open —
    re-surface the same RequestPayment so ASI:One re-renders the overlay."""
    checkout_id = pending.get("checkout_session_id") or ""
    urls = list(pending.get("parsed", {}).get("youtube_urls") or [])

    # If Stripe already marked the session paid (e.g. webhook lag, user
    # confirmed but CommitPayment hasn't landed yet), release the pipeline.
    try:
        paid = await asyncio.to_thread(_verify_checkout_session_paid, checkout_id)
    except Exception as exc:
        ctx.logger.warning(f"[Payment] Could not re-verify pending checkout: {exc}")
        paid = False
    if paid:
        ctx.logger.info("[Payment] Pending checkout already paid — releasing pipeline")
        parsed = pending.get("parsed") or {}
        _clear_pending(ctx, sender)
        await _run_travel_pipeline(ctx, sender, parsed)
        return

    # Rebuild the Stripe payload.  The embedded Stripe.js SDK requires
    # the live `client_secret` AND the underlying Session must itself
    # have been created with ui_mode="embedded" — you cannot mount a
    # page-mode session inline.  So we retrieve the stored session,
    # verify its ui_mode matches, and mint a fresh embedded session
    # whenever anything is off (expired, wrong mode, missing secret).
    client_secret: str | None = None
    stored_ui_mode: str | None = None
    stored_status: str | None = None
    try:
        if _stripe_lib is not None:
            _stripe_lib.api_key = _STRIPE_SECRET_KEY  # type: ignore[union-attr]
            sess = await asyncio.to_thread(
                _stripe_lib.checkout.Session.retrieve,  # type: ignore[union-attr]
                checkout_id,
            )
            client_secret = getattr(sess, "client_secret", None)
            stored_ui_mode = getattr(sess, "ui_mode", None)
            stored_status = getattr(sess, "status", None)
    except Exception as exc:
        ctx.logger.warning(
            f"[Payment] Could not retrieve client_secret for retry: {exc}"
        )

    needs_fresh = (
        not client_secret
        or stored_ui_mode != "embedded_page"
        or stored_status not in (None, "open")
    )
    if needs_fresh:
        ctx.logger.info(
            f"[Payment] Minting fresh embedded checkout for retry "
            f"(old ui_mode={stored_ui_mode}, status={stored_status}, "
            f"has_secret={bool(client_secret)})"
        )
        try:
            fresh = await asyncio.to_thread(
                _create_embedded_checkout,
                user_address=sender,
                chat_session_id=str(ctx.session),
                description=(f"Retry: curate a {_count_description(urls)} road trip."),
            )
        except Exception as exc:
            ctx.logger.error(f"[Payment] Retry checkout create failed: {exc}")
            await send_final(
                ctx,
                sender,
                "I couldn't re-open the Stripe checkout just now — please "
                "try again in a moment.",
            )
            return
        pending["checkout_session_id"] = fresh["checkout_session_id"]
        _save_pending(ctx, sender, pending)
        checkout_payload = fresh
    else:
        checkout_payload = {
            "client_secret": client_secret,
            "checkout_session_id": checkout_id,
            "id": checkout_id,
            "publishable_key": _STRIPE_PUBLISHABLE,
            "currency": _STRIPE_CURRENCY,
            "amount_cents": _STRIPE_PRICE_CENTS,
            "ui_mode": "embedded_page",
        }
    await ctx.send(
        sender,
        RequestPayment(
            accepted_funds=[
                Funds(
                    currency=_STRIPE_CURRENCY.upper(),
                    amount=f"{_STRIPE_PRICE_CENTS / 100:.2f}",
                    payment_method="stripe",
                )
            ],
            recipient=str(ctx.agent.address),
            deadline_seconds=_STRIPE_CHECKOUT_EXPIRES_S,
            reference=str(ctx.session),
            description=(
                f"Pay {_price_display()} to generate your trip plan from "
                f"{len(urls)} video{'s' if len(urls) != 1 else ''}."
            ),
            metadata={"stripe": checkout_payload, "service": "travel_map_agent"},
        ),
    )
    ctx.logger.info(
        f"[Payment] RequestPayment RESENT "
        f"(checkout={checkout_payload['checkout_session_id'][:20]}..., "
        f"ui_mode={checkout_payload['ui_mode']}, "
        f"has_secret={bool(checkout_payload.get('client_secret'))})"
    )
    await ctx.send(
        sender,
        ChatMessage(
            msg_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"Still waiting on payment — complete the Stripe checkout "
                        f"above to release your trip plan ({_price_display()})."
                    ),
                )
            ],
        ),
    )


def _count_description(urls: list) -> str:
    n = len(urls or [])
    if n <= 1:
        return "single-video"
    return f"{n}-video"


async def _run_travel_pipeline(ctx: Context, sender: str, parsed: dict) -> None:
    """The real workflow: transcripts → location extraction → aggregator
    → trip planner → weather snapshot → PDF + Excel → final chat reply.

    Called directly when Stripe is disabled, or from on_commit_payment
    once a checkout has been verified as paid.
    """
    youtube_urls = parsed.get("youtube_urls", []) or []
    trip_date: str = str(parsed.get("trip_date") or "")
    trip_title = parsed.get("trip_title", "Road Trip Itinerary")
    preferences = parsed.get("preferences", "")
    budget_per_day = float(parsed.get("budget_per_day", 0.0) or 0.0)
    total_budget = float(parsed.get("total_budget", 0.0) or 0.0)
    trip_days = int(parsed.get("trip_days", 0) or 0)

    if not youtube_urls:
        # Sanity guard — the caller should have filtered these out already.
        await send_final(
            ctx,
            sender,
            "No YouTube URLs found in the saved request. Please resend "
            "with your travel vlog links included.",
        )
        return

    # step 2 — fan out transcript + location extraction across N videos
    await send_status(
        ctx,
        sender,
        f"Processing {len(youtube_urls)} video(s) in parallel: "
        "fetching transcripts and extracting locations...",
    )

    async def _process_one_video(idx: int, url: str) -> dict:
        """Run transcript + location extraction for a single URL.
        Returns a dict the aggregator can consume even on partial failure."""
        result = {
            "video_index": idx,
            "url": url,
            "video_title": "",
            "channel_name": "",
            "thumbnail_url": "",
            "locations": [],
            "transcript_chars": 0,
            "error": None,
        }
        try:
            tr_resp, _ = await ctx.send_and_receive(
                TRANSCRIPT_AGENT_ADDR,
                TranscriptRequest(youtube_url=url),
                response_type=TranscriptResponse,
                timeout=60,
            )
        except Exception as e:
            result["error"] = f"transcript timeout: {e}"
            return result
        if not isinstance(tr_resp, TranscriptResponse) or not tr_resp.success:
            result["error"] = (
                tr_resp.error
                if isinstance(tr_resp, TranscriptResponse)
                else "transcript agent did not respond"
            )
            return result

        result["video_title"] = tr_resp.video_title or ""
        result["channel_name"] = tr_resp.channel_name or ""
        result["thumbnail_url"] = tr_resp.thumbnail_url or ""
        result["transcript_chars"] = len(tr_resp.transcript or "")

        try:
            loc_resp, _ = await ctx.send_and_receive(
                LOCATION_AGENT_ADDR,
                LocationExtractionRequest(text=tr_resp.transcript),
                response_type=LocationExtractionResponse,
                timeout=60,
            )
        except Exception as e:
            result["error"] = f"location extractor timeout: {e}"
            return result
        if isinstance(loc_resp, LocationExtractionResponse):
            result["locations"] = loc_resp.locations or []
        return result

    video_results = await asyncio.gather(
        *[_process_one_video(i, u) for i, u in enumerate(youtube_urls)],
        return_exceptions=False,
    )

    successful = [v for v in video_results if not v["error"] and v["locations"]]
    failed = [v for v in video_results if v["error"] or not v["locations"]]
    if not successful:
        msgs = "; ".join(
            f"{v['url']}: {v['error'] or 'no locations extracted'}" for v in failed
        )
        await send_final(
            ctx,
            sender,
            f"Couldn't get usable locations from any of your videos.\n\n{msgs}",
        )
        return

    total_extracted = sum(len(v["locations"]) for v in successful)
    ctx.logger.info(
        f"Extracted {total_extracted} raw locations across "
        f"{len(successful)} video(s)" + (f" ({len(failed)} failed)" if failed else "")
    )

    # step 3 — aggregator agent (dedupe + Places lookup + score)
    if not AGGREGATOR_AGENT_ADDR:
        await send_final(
            ctx,
            sender,
            "Aggregator agent address is not configured. "
            "Start aggregator_agent.py and set AGGREGATOR_AGENT_ADDR in .env.",
        )
        return

    try:
        agg_resp, _status = await ctx.send_and_receive(
            AGGREGATOR_AGENT_ADDR,
            AggregateRequest(videos=successful),
            response_type=AggregateResponse,
            timeout=180,
        )
    except Exception as e:
        await send_final(ctx, sender, f"Aggregator timed out: {e}")
        return
    if not isinstance(agg_resp, AggregateResponse) or not agg_resp.success:
        err = (
            agg_resp.error
            if isinstance(agg_resp, AggregateResponse)
            else f"no response (status={_status})"
        )
        await send_final(ctx, sender, f"Aggregator failed: {err}")
        return

    if not agg_resp.ranked_stops:
        await send_final(
            ctx,
            sender,
            "None of the extracted locations could be validated in "
            "Google Places after deduping. Try videos with more specific "
            "place names.",
        )
        return

    consensus_count = sum(
        1 for s in agg_resp.ranked_stops if s.get("frequency", 1) >= 2
    )

    # step 4 — trip planner agent (curates + clusters + adds restaurants)
    if not TRIP_PLANNER_AGENT_ADDR:
        await send_final(
            ctx,
            sender,
            "Trip planner agent address is not configured. "
            "Start trip_planner_agent.py and set TRIP_PLANNER_AGENT_ADDR in .env.",
        )
        return

    budget_summary = (
        f"${total_budget:.0f} total"
        if total_budget > 0
        else (f"${budget_per_day:.0f}/day" if budget_per_day > 0 else "default budget")
    )
    ctx.logger.info(
        f"Ranked {len(agg_resp.ranked_stops)} unique stops "
        f"({consensus_count} in >=2 videos) — curating with {budget_summary}"
    )

    try:
        planner_resp, _status = await ctx.send_and_receive(
            TRIP_PLANNER_AGENT_ADDR,
            TripPlannerRequest(
                validated_stops=agg_resp.ranked_stops,
                budget_per_day=budget_per_day,
                total_budget=total_budget,
                trip_days=trip_days,
                trip_start_date=trip_date,
                preferences=preferences,
            ),
            response_type=TripPlannerResponse,
            timeout=180,
        )
    except Exception as e:
        await send_final(ctx, sender, f"Trip planner timed out: {e}")
        return
    if not isinstance(planner_resp, TripPlannerResponse):
        await send_final(ctx, sender, f"Trip planner failed (status={_status})")
        return
    if not planner_resp.success or not planner_resp.days:
        await send_final(
            ctx,
            sender,
            f"Trip planner couldn't build a plan: "
            f"{planner_resp.error or 'unknown error'}",
        )
        return

    # Rebuild Google Maps URL from only the curated stops — the geocoder's
    # URL includes every raw match, which is usually way too many.
    curated_maps_url = build_maps_url_from_planned(planner_resp.days)
    curated_stops = _flatten_planned_stops(planner_resp.days)

    # step 6 — initial weather snapshot (synchronous, one-shot). Failure
    # here is non-fatal: the pipeline continues and the PDF/chat just omit
    # per-stop forecasts. Background monitoring still kicks in at step 8.
    ctx.logger.info(
        f"Plan ready: {len(planner_resp.days)} day(s), "
        f"{len(curated_stops)} stops. Checking initial weather for "
        f"{trip_date}..."
    )
    initial_forecasts_by_name: dict = {}
    snapshot_resp: WeatherSnapshotResponse | None = None
    try:
        snapshot_resp_raw, _status = await ctx.send_and_receive(
            WEATHER_AGENT_ADDR,
            WeatherSnapshotRequest(
                stops=curated_stops,
                trip_start_date=trip_date,
            ),
            response_type=WeatherSnapshotResponse,
            timeout=60,
        )
        if (
            isinstance(snapshot_resp_raw, WeatherSnapshotResponse)
            and snapshot_resp_raw.success
        ):
            snapshot_resp = snapshot_resp_raw
            initial_forecasts_by_name = {
                f.get("name", ""): f for f in snapshot_resp.forecasts
            }
        else:
            ctx.logger.warning(
                f"Weather snapshot unavailable (status={_status}); "
                f"continuing without initial forecast."
            )
    except Exception as e:
        ctx.logger.warning(f"Weather snapshot error: {e} (continuing)")

    # Use the first video's metadata for the PDF cover when only one video
    # was supplied; otherwise fall back to the curated trip title and skip
    # per-video cover details.
    cover_video_title = (
        successful[0].get("video_title", "") if len(successful) == 1 else ""
    )
    cover_channel_name = (
        successful[0].get("channel_name", "") if len(successful) == 1 else ""
    )
    cover_thumbnail = (
        successful[0].get("thumbnail_url", "") if len(successful) == 1 else ""
    )

    fallback_maps_url = curated_maps_url or agg_resp.maps_url

    # step 7 — PDF generator agent
    ctx.logger.info(
        f"Generating PDF travel guide (est. "
        f"${planner_resp.total_estimated_cost:.0f})..."
    )
    try:
        pdf_resp, _status = await ctx.send_and_receive(
            PDF_AGENT_ADDR,
            PDFRequest(
                planned_days=planner_resp.days,
                maps_url=fallback_maps_url,
                trip_title=trip_title,
                trip_start_date=trip_date,
                total_estimated_cost=planner_resp.total_estimated_cost,
                video_title=cover_video_title,
                channel_name=cover_channel_name,
                thumbnail_url=cover_thumbnail,
                preferences=preferences,
                initial_forecasts=initial_forecasts_by_name,
            ),
            response_type=PDFResponse,
            timeout=180,
        )
        if not isinstance(pdf_resp, PDFResponse):
            raise RuntimeError(
                f"PDF agent returned no valid response (status={_status})"
            )
    except Exception as e:
        ctx.logger.error(f"PDF agent timed out: {e}")
        pdf_resp = PDFResponse(success=False, error=str(e))

    pdf_filename = pdf_resp.pdf_filename if pdf_resp.success else "N/A"
    pdf_path = pdf_resp.pdf_path if pdf_resp.success else None

    # step 8 — Excel generator agent (live planning workbook: itinerary,
    # restaurants, budget, weather log, maps). Non-fatal on failure.
    excel_filename = None
    excel_path = None
    if EXCEL_AGENT_ADDR:
        ctx.logger.info("Building the live planning Excel workbook...")
        try:
            excel_resp, _status = await ctx.send_and_receive(
                EXCEL_AGENT_ADDR,
                ExcelRequest(
                    planned_days=planner_resp.days,
                    maps_url=fallback_maps_url,
                    trip_title=trip_title,
                    trip_start_date=trip_date,
                    total_estimated_cost=planner_resp.total_estimated_cost,
                    budget_per_day=(
                        budget_per_day
                        if budget_per_day > 0
                        else (
                            total_budget / max(1, planner_resp.derived_trip_days)
                            if total_budget > 0
                            else 100.0
                        )
                    ),
                    video_title=cover_video_title,
                    channel_name=cover_channel_name,
                    preferences=preferences,
                    initial_forecasts=initial_forecasts_by_name,
                ),
                response_type=ExcelResponse,
                timeout=60,
            )
            if isinstance(excel_resp, ExcelResponse) and excel_resp.success:
                excel_filename = excel_resp.excel_filename
                excel_path = excel_resp.excel_path
            else:
                ctx.logger.warning(
                    f"Excel agent returned no valid response (status={_status})"
                )
        except Exception as e:
            ctx.logger.error(f"Excel agent error: {e}")
    else:
        ctx.logger.warning(
            "EXCEL_AGENT_ADDR not set — skipping Excel generation. "
            "Start excel_generator_agent.py and fill EXCEL_AGENT_ADDR in .env."
        )

    # step 9 — start weather monitor on the curated stops only. Pass the
    # excel path so the monitor can append daily check rows to it.
    try:
        await ctx.send(
            WEATHER_AGENT_ADDR,
            WeatherMonitorRequest(
                stops=curated_stops,
                trip_start_date=trip_date,
                user_sender_address=sender,
                excel_path=excel_path,
            ),
        )
        ctx.logger.info("Weather monitor started")
    except Exception as e:
        ctx.logger.error(f"Weather monitor failed to start: {e}")

    # step 10 — materialise the route map PNG into output/ so we can
    # serve it as a clickable link.  We follow the pdf-podcast-agent
    # approach: PDF + Excel + Map are saved in output/ and surfaced as
    # markdown URLs pointing at our local HTTP file server (which
    # ASI:One's chat UI renders reliably as clickable download links).
    map_filename: str | None = None
    map_png_bytes: bytes | None = None
    if _GOOGLE_MAPS_API_KEY and curated_stops:
        ctx.logger.info("Rendering the route map preview...")
        try:
            png = await asyncio.to_thread(
                _fetch_static_map_png,
                ctx,
                curated_stops,
            )
        except Exception as exc:
            ctx.logger.warning(f"[Map] PNG fetch failed: {exc}")
            png = None
        if png:
            map_png_bytes = png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            map_filename = f"trip_map_{ts}.png"
            try:
                (_OUTPUT_DIR / map_filename).write_bytes(png)
            except Exception as exc:
                ctx.logger.warning(
                    f"[Map] could not persist PNG to {map_filename}: {exc}"
                )
                map_filename = None

    # Build the public download URLs (served by the local files HTTP
    # server we start at module import time).
    map_url = _file_url(map_filename) if map_filename else None
    pdf_url = _file_url(pdf_path) if pdf_path else None
    excel_url = _file_url(excel_path) if excel_path else None

    # Upload the map PNG to Agentverse storage so it renders as a native
    # image attachment in ASI:One chat.  Retry once on transient network
    # errors.  If both attempts fail, fall back to a base64 data URI
    # embedded directly in the Markdown text.
    map_resource: ResourceContent | None = None
    map_data_uri: str | None = None
    if map_png_bytes and map_filename:
        for attempt in range(2):
            try:
                map_resource = await asyncio.to_thread(
                    _upload_file_as_resource,
                    ctx,
                    sender,
                    str(_OUTPUT_DIR / map_filename),
                    filename=map_filename,
                    mime_type="image/png",
                    role="trip-map-preview",
                    extra_metadata={
                        "link_url": fallback_maps_url,
                        "click_url": fallback_maps_url,
                        "target_uri": fallback_maps_url,
                        "caption": "Route map preview — click to open in Google Maps",
                    },
                )
                if map_resource:
                    break
            except Exception as exc:
                ctx.logger.warning(
                    f"[Map] Agentverse upload attempt {attempt + 1} failed: {exc}"
                )
                if attempt == 0:
                    await asyncio.sleep(2)
        if not map_resource and len(map_png_bytes) <= 900_000:
            ctx.logger.info("[Map] Falling back to base64 data URI")
            map_data_uri = "data:image/png;base64," + base64.b64encode(
                map_png_bytes
            ).decode("ascii")

    # step 10b — resolve public HTTPS photo URLs for each unique stop
    # so they can be embedded inline in the Markdown text.
    photo_urls: dict[str, str] = {}
    if _GOOGLE_MAPS_API_KEY:
        flat_stops = _flatten_planned_stops(planner_resp.days)
        seen_names: set[str] = set()
        unique_stops: list[dict] = []
        for s in flat_stops:
            if s.get("photo_reference") and s["name"] not in seen_names:
                seen_names.add(s["name"])
                unique_stops.append(s)

        if unique_stops:
            ctx.logger.info(f"Resolving photo URLs for {len(unique_stops)} stop(s)...")

            async def _resolve_url(stop: dict) -> tuple[str, str | None]:
                url = await asyncio.to_thread(
                    _resolve_place_photo_url,
                    stop["photo_reference"],
                )
                return stop["name"], url

            results = await asyncio.gather(
                *[_resolve_url(s) for s in unique_stops],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, tuple) and r[1]:
                    photo_urls[r[0]] = r[1]
            ctx.logger.info(f"Resolved {len(photo_urls)} place photo URL(s)")

    # step 11 — format final reply with ASI1
    final_text = format_final_response(
        planner_resp,
        pdf_filename,
        trip_date,
        preferences,
        successful,  # video summaries (list of dicts)
        snapshot_resp,
        user_total_budget=total_budget,
    )

    # step 11b — inject stop thumbnail photos into the consensus section.
    # Done as post-processing so the LLM never sees the long CDN URLs.
    final_text = _inject_stop_photos(final_text, photo_urls)

    # ── Tail-of-message assembly ───────────────────────────────────────
    # The map PNG is attached via ResourceContent (rendered natively by
    # ASI:One as an inline image).  The text block below just carries
    # the clickable Google Maps link.
    links_block: list[str] = ["", "## Your trip package"]
    if map_resource:
        links_block += [
            "",
            f"- **Route map**: [open interactive Google Maps directions]"
            f"({fallback_maps_url})",
        ]
    elif map_data_uri:
        links_block += [
            "",
            f"![Route map preview]({map_data_uri})",
            "",
            f"- **Route map**: [open interactive Google Maps directions]"
            f"({fallback_maps_url})",
        ]
    elif map_url:
        links_block += [
            "",
            f"- **Route map**: [open the static route map]({map_url}) · "
            f"[open interactive Google Maps directions]"
            f"({fallback_maps_url})",
        ]
    else:
        links_block += [
            "",
            f"- **Route map**: [open Google Maps directions]" f"({fallback_maps_url})",
        ]
    if pdf_url:
        links_block.append(
            f"- **PDF travel guide**: [download {pdf_filename}]({pdf_url})"
        )
    elif pdf_filename and pdf_filename != "N/A":
        links_block.append(
            f"- **PDF travel guide** saved locally at " f"`output/{pdf_filename}`"
        )
    if excel_url:
        links_block.append(
            f"- **Excel planning workbook** "
            f"(itinerary · restaurants · budget · weather · maps): "
            f"[download {excel_filename}]({excel_url})"
        )
    elif excel_filename:
        links_block.append(
            f"- **Excel planning workbook** saved locally at "
            f"`output/{excel_filename}`"
        )

    if len(links_block) > 2:
        final_text += "\n" + "\n".join(links_block)
    attachments: list = []
    if map_resource:
        attachments.append(map_resource)

    # If the file server isn't reachable externally but the user pasted
    # a public URL in FILES_PUBLIC_BASE, give them a hint; otherwise
    # assume same-machine testing and move on.
    if not (map_url or pdf_url or excel_url):
        final_text += (
            "\n\n(Files saved in the local output/ folder — the built-in "
            "download server couldn't expose them; set FILES_PUBLIC_BASE "
            "in .env or open the files directly from disk.)"
        )

    # Processing caveats (unmatched locations, failed videos) kept subtle
    # at the very end of the message.
    extras = []
    if agg_resp.skipped_count > 0:
        extras.append(
            f"{agg_resp.skipped_count} raw location mention"
            f"{'s' if agg_resp.skipped_count != 1 else ''} "
            f"couldn't be matched in Google Places."
        )
    if failed:
        extras.append(
            f"{len(failed)} video(s) couldn't be processed "
            f"(missing captions or timed out)."
        )
    if extras:
        final_text += "\n\nNote: " + " ".join(extras)

    await send_final(ctx, sender, final_text, attachments=attachments)


# ── Agent Payment Protocol (Stripe embedded checkout) ────────────────────────

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")


@payment_proto.on_message(CommitPayment)
async def on_commit_payment(ctx: Context, sender: str, msg: CommitPayment) -> None:
    """User completed the Stripe embedded checkout.

    ASI:One sends `CommitPayment(transaction_id=<Stripe Checkout Session ID>)`.
    We verify with Stripe, acknowledge with `CompletePayment`, and then
    release the saved pending state into the real workflow.
    """
    if msg.funds.payment_method != "stripe" or not msg.transaction_id:
        await ctx.send(
            sender,
            RejectPayment(
                reason="Unsupported payment method (expected stripe).",
            ),
        )
        return

    checkout_session_id = msg.transaction_id
    try:
        paid = await asyncio.to_thread(
            _verify_checkout_session_paid,
            checkout_session_id,
        )
    except Exception as exc:
        ctx.logger.error(f"[Payment] Stripe verify error: {exc}")
        await ctx.send(
            sender,
            RejectPayment(
                reason="Could not verify payment with Stripe. Please try again.",
            ),
        )
        return

    if not paid:
        await ctx.send(
            sender,
            RejectPayment(
                reason="Stripe payment not completed yet. Please finish checkout.",
            ),
        )
        return

    await ctx.send(sender, CompletePayment(transaction_id=checkout_session_id))
    ctx.logger.info(
        f"[Payment] CompletePayment sent for checkout={checkout_session_id[:20]}..."
    )

    # Load the parsed-intent blob we stashed when issuing the RequestPayment.
    # The sender address on CommitPayment is the same buyer agent address
    # we keyed pending state against, so load by sender.
    pending = _load_pending(ctx, sender)
    if not pending or pending.get("checkout_session_id") != checkout_session_id:
        # Fallback: look up the original chat_session_id on the Stripe
        # metadata in case our local state expired or was cleared by
        # another handler; we can't resume without the parsed intent
        # though, so just inform the user.
        ctx.logger.warning(
            "[Payment] Paid checkout has no matching pending state "
            f"(checkout={checkout_session_id[:20]}...). Asking user to retry."
        )
        await ctx.send(
            sender,
            ChatMessage(
                msg_id=uuid4(),
                timestamp=datetime.now(timezone.utc),
                content=[
                    TextContent(
                        type="text",
                        text=(
                            "Payment received, but I couldn't find the original trip "
                            "request linked to this checkout. Please resend your "
                            "YouTube URLs and preferences and I'll rerun the plan on "
                            "your already-paid credit."
                        ),
                    )
                ],
            ),
        )
        return

    parsed = pending.get("parsed") or {}
    _clear_pending(ctx, sender)

    await ctx.send(
        sender,
        ChatMessage(
            msg_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"Payment confirmed ({_price_display()}). Releasing the "
                        "workflow now — hang tight while I process your videos."
                    ),
                )
            ],
        ),
    )
    await _run_travel_pipeline(ctx, sender, parsed)


@payment_proto.on_message(RejectPayment)
async def on_reject_payment(ctx: Context, sender: str, msg: RejectPayment) -> None:
    """User cancelled or the UI rejected the payment."""
    ctx.logger.info(f"[Payment] Payment rejected by {sender[:20]}...: {msg.reason}")
    _clear_pending(ctx, sender)
    await ctx.send(
        sender,
        ChatMessage(
            msg_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"Payment was cancelled or rejected. {msg.reason or ''}\n\n"
                        "Send me another message with your YouTube URLs whenever "
                        "you're ready to try again."
                    ).strip(),
                )
            ],
        ),
    )


agent.include(chat_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)


def _assert_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
        except OSError as e:
            raise SystemExit(
                f"Port {port} is already in use. Stop the other Python/orchestrator "
                f"using it, or set ORCHESTRATOR_PORT to a free port and set "
                f"ORCHESTRATOR_ENDPOINT to match (e.g. "
                f"http://127.0.0.1:<port>/submit). Original error: {e}"
            ) from e


if __name__ == "__main__":
    _assert_port_available(_ORCHESTRATOR_PORT)
    agent.run()

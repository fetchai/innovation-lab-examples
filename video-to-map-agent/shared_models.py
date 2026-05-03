from uagents import Model
from typing import List, Dict, Optional


# ── Transcript ────────────────────────────────────────────────────────────────


class TranscriptRequest(Model):
    youtube_url: str


class TranscriptResponse(Model):
    success: bool
    transcript: Optional[str] = None
    error: Optional[str] = None
    video_title: Optional[str] = None
    channel_name: Optional[str] = None
    thumbnail_url: Optional[str] = None


# ── Location extraction ───────────────────────────────────────────────────────


class LocationExtractionRequest(Model):
    text: str


class LocationExtractionResponse(Model):
    locations: List[str]


# ── Geocoding ─────────────────────────────────────────────────────────────────


class GeocodeRequest(Model):
    locations: List[str]


class GeocodeResponse(Model):
    validated_stops: List[Dict]
    maps_url: str
    skipped_count: int


# ── Aggregator ────────────────────────────────────────────────────────────────
# When the user pastes multiple YouTube URLs in one message we run transcript
# + location extraction on each video in parallel, then funnel every per-video
# location list through the Aggregator. It dedupes across videos, calls
# Google Places once per unique name to validate + grab the rating, then
# scores by (cross-video frequency × Places rating) and returns a ranked list
# the trip planner can consume directly.


class VideoLocations(Model):
    """One per analysed YouTube video."""

    video_index: int
    video_title: str = ""
    channel_name: str = ""
    locations: List[str] = []


class AggregateRequest(Model):
    videos: List[Dict]  # each item shaped like VideoLocations.dict()


class AggregateResponse(Model):
    success: bool
    # Each entry has ALL the fields the trip planner / geocoder would have
    # produced PLUS scoring metadata so the planner can prefer consensus stops:
    #
    # {
    #   "name": str, "address": str, "lat": float, "lng": float,
    #   "place_id": str, "rating": float,
    #   "frequency": int,                  # how many videos mentioned it
    #   "mentioned_in_videos": [int, ...], # 0-based video indices
    #   "score": float,                    # 60% freq + 40% rating, scaled 0-100
    # }
    ranked_stops: List[Dict] = []
    # Useful summary fields the orchestrator surfaces back to the user.
    total_unique_locations: int = 0
    total_raw_mentions: int = 0
    skipped_count: int = 0
    maps_url: str = ""
    error: Optional[str] = None


# ── Trip planner ──────────────────────────────────────────────────────────────
# The trip planner takes the ranked stops from the aggregator plus the user's
# constraints (budget, days, preferences) and returns a curated, day-by-day
# itinerary. Structured dicts are used for portability across uagents message
# boundaries — nested Model classes get flattened too aggressively by pydantic.
#
# Budget handling is flexible:
#   • If the user gave a per-day budget AND a number of days → use both.
#   • If only total_budget → planner derives days from total / est. daily cost.
#   • If only budget_per_day → planner uses provided trip_days (default 3).
#   • If neither → defaults of $100/day and 3 days.


class TripPlannerRequest(Model):
    validated_stops: List[Dict]
    budget_per_day: float = 0.0  # 0 means "not specified"
    total_budget: float = 0.0  # 0 means "not specified"
    trip_days: int = 0  # 0 means "let the planner decide"
    trip_start_date: str = ""
    preferences: str = ""


class TripPlannerResponse(Model):
    success: bool
    # Each entry has shape:
    # {
    #   "day_number": int,
    #   "theme": str,
    #   "estimated_cost_usd": float,
    #   "stops": [
    #     {
    #       "name": str, "address": str, "lat": float, "lng": float,
    #       "place_id": str,
    #       "activity": str,           # what to do here
    #       "duration_hours": int,     # rough time budget
    #       "nearby_restaurants": [    # filtered by preferences (e.g. vegetarian)
    #         {"name": str, "address": str, "rating": float}
    #       ],
    #     },
    #     ...
    #   ]
    # }
    days: List[Dict] = []
    total_estimated_cost: float = 0.0
    reasoning: str = ""
    # Echoed back so the orchestrator can tell the user "fits your budget"
    # vs "tight" vs "would need more days".
    budget_assessment: str = ""  # "fits" | "tight" | "over"
    derived_trip_days: int = 0  # the day count the planner actually used
    error: Optional[str] = None


# ── Weather monitor ───────────────────────────────────────────────────────────


class WeatherMonitorRequest(Model):
    stops: List[Dict]
    trip_start_date: str
    user_sender_address: str
    # Optional absolute path to an .xlsx file the weather agent should
    # append its daily check rows to (Sheet "Weather Monitor Log"). If
    # omitted the agent just monitors without touching disk.
    excel_path: Optional[str] = None


class WeatherMonitorResponse(Model):
    status: str


class WeatherSnapshotRequest(Model):
    """Ask the weather agent for a one-shot forecast for each stop on the
    trip's start date. Distinct from WeatherMonitorRequest, which starts a
    daily background watch; this one returns immediately."""

    stops: List[Dict]
    trip_start_date: str


class WeatherSnapshotResponse(Model):
    success: bool
    # Each entry matches one stop, same order as the request:
    # {
    #   "name": str, "lat": float, "lng": float,
    #   "condition": str,           # short human-readable label
    #   "high_c": float | None,     # daily max (Celsius)
    #   "low_c": float | None,      # daily min (Celsius)
    #   "precip_percent": int,
    #   "wind_kmh": float,
    #   "thunderstorm_percent": int,
    #   "bad": bool,                # true if is_bad_forecast() flags it
    #   "warning": str,             # non-empty if bad=True
    #   "available": bool,          # false if Google Weather returned nothing
    # }
    forecasts: List[Dict] = []
    error: Optional[str] = None


# ── PDF generation ────────────────────────────────────────────────────────────
# The PDF generator now renders a day-by-day itinerary instead of a flat list
# of stops. `planned_days` matches TripPlannerResponse.days exactly.


class PDFRequest(Model):
    planned_days: List[Dict]
    maps_url: str
    trip_title: str
    trip_start_date: str
    total_estimated_cost: float = 0.0
    video_title: Optional[str] = None
    channel_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    preferences: Optional[str] = None
    # Optional initial forecasts, keyed by stop name. Each value has the
    # same shape as one entry in WeatherSnapshotResponse.forecasts.
    initial_forecasts: Dict = {}


class PDFResponse(Model):
    success: bool
    pdf_filename: Optional[str] = None
    pdf_path: Optional[str] = None  # absolute path; needed to attach it to chat
    error: Optional[str] = None


# ── Excel generation ──────────────────────────────────────────────────────────
# Parallel to the PDF agent: takes the same curated inputs and produces a
# multi-sheet workbook the traveller can use as a live planning tool.


class ExcelRequest(Model):
    planned_days: List[Dict]
    maps_url: str
    trip_title: str
    trip_start_date: str
    total_estimated_cost: float = 0.0
    budget_per_day: float = 100.0
    video_title: Optional[str] = None
    channel_name: Optional[str] = None
    preferences: Optional[str] = None
    initial_forecasts: Dict = {}


class ExcelResponse(Model):
    success: bool
    excel_filename: Optional[str] = None
    excel_path: Optional[str] = None  # absolute path; handy for the weather agent
    error: Optional[str] = None

"""Build ASI:One interactive cards and chat messages."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    TextContent,
)


def card_message(
    card_kind: str, card_payload: dict, narration: str = ""
) -> ChatMessage:
    content = [
        MetadataContent(
            type="metadata",
            metadata={
                "card_protocol_version": "1",
                "requires_card_interaction": "true",
                "card_kind": card_kind,
                "card_payload": json.dumps(card_payload),
                "preferred_drawer_width_px": "540",
            },
        ),
    ]
    if narration:
        content.insert(0, TextContent(type="text", text=narration))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )


def text_message(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )


def info_card(
    title: str,
    body: str,
    button_label: str | None = None,
    button_action: dict | None = None,
) -> dict:
    children: list[dict] = [{"type": "text", "value": body, "style": "muted"}]
    if button_label and button_action:
        children.append(
            {
                "type": "button",
                "label": button_label,
                "primary": True,
                "action": {"selection": button_action},
            }
        )
    return {"root": {"type": "section", "title": title, "children": children}}


def error_card(message: str) -> dict:
    return info_card(
        "Something went wrong", message, "Search again", {"action": "back"}
    )


def search_form_card() -> dict:
    return {
        "title": "Plan your trip",
        "fields": [
            {
                "name": "trip_type",
                "kind": "select",
                "label": "What do you need?",
                "options": [
                    {"value": "flight", "label": "Flights only"},
                    {"value": "hotel", "label": "Hotel only"},
                    {"value": "package", "label": "Flight + Hotel"},
                ],
            },
            {"name": "origin", "kind": "text", "label": "From (city or IATA)"},
            {
                "name": "destination",
                "kind": "text",
                "label": "To (city or IATA)",
                "required": True,
            },
            {
                "name": "departure_date",
                "kind": "text",
                "label": "Check-in / Depart (YYYY-MM-DD)",
                "required": True,
            },
            {
                "name": "return_date",
                "kind": "text",
                "label": "Check-out / Return (YYYY-MM-DD)",
            },
            {"name": "adults", "kind": "number", "label": "Adults", "required": True},
        ],
        "submit_cta": {"label": "Search", "selection": {"action": "submit_search"}},
    }


def booking_review_card(title: str, summary_rows: list, book_url: str) -> dict:
    return {
        "title": title or "Confirm your booking",
        "summary_rows": summary_rows,
        "approve_cta": {
            "label": "Approve",
            "primary": True,
            "selection": {"action": "approve", "book_url": book_url},
        },
        "reject_cta": {"label": "Cancel", "selection": {"action": "cancel"}},
    }


def booking_redirect_card(title: str, book_url: str) -> dict:
    return {
        "root": {
            "type": "section",
            "title": "Complete your booking",
            "children": [
                {
                    "type": "text",
                    "value": f"Tap below to open **{title}** on lastminute.com in a new tab.",
                    "style": "muted",
                },
                {
                    "type": "button",
                    "label": "Book on lastminute.com →",
                    "primary": True,
                    "action": {
                        "selection": {"action": "book_opened"},
                        "redirect": book_url,
                    },
                },
            ],
        }
    }


def passenger_details_form_card() -> dict:
    return {
        "root": {
            "type": "section",
            "title": "Passenger details",
            "children": [
                {
                    "type": "input",
                    "name": "first_name",
                    "kind": "text",
                    "label": "First name",
                    "required": True,
                },
                {
                    "type": "input",
                    "name": "email",
                    "kind": "email",
                    "label": "Email",
                    "required": True,
                },
                {
                    "type": "input",
                    "name": "departure",
                    "kind": "date",
                    "label": "Departure",
                    "minimum": "2026-06-01",
                    "maximum": "2026-12-31",
                },
                {
                    "type": "input",
                    "name": "pickup_time",
                    "kind": "time",
                    "label": "Pickup time",
                    "default": "10:30",
                },
                {
                    "type": "input",
                    "name": "phone",
                    "kind": "phone",
                    "label": "Phone",
                    "default": "+447788998877",
                },
                {
                    "type": "input",
                    "name": "country",
                    "kind": "select",
                    "label": "Country",
                    "options": [{"value": "GB", "label": "United Kingdom"}],
                },
                {
                    "type": "input",
                    "name": "extras",
                    "kind": "multiselect",
                    "label": "Add-ons",
                    "options": [
                        {"value": "bag", "label": "Extra bag"},
                        {"value": "meal", "label": "Meal"},
                    ],
                },
                {
                    "type": "button",
                    "label": "Continue",
                    "primary": True,
                    "action": {"selection": {"action": "submit"}},
                },
                {
                    "type": "button",
                    "label": "Cancel",
                    "action": {
                        "selection": {"action": "cancel"},
                        "bypass_required_validation": True,
                    },
                },
            ],
        }
    }


def detail_card(title: str, summary_rows: list, book_url: str) -> dict:
    return {
        "title": title,
        "summary_rows": summary_rows,
        "ctas": [
            {
                "label": "Open booking page →",
                "primary": True,
                "selection": {"action": "open_book", "book_url": book_url},
            },
            {"label": "← Back", "selection": {"action": "back"}},
        ],
    }

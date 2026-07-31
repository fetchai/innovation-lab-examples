from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    MetadataContent,
    TextContent,
    chat_protocol_spec,
)

import payment
from pydantic_agent import (
    PackageDetails,
    SenderProfile,
    ShippingDeps,
    extract_package,
    extract_sender_profile,
    resume_purchase,
    start_purchase,
)
from session_state import (
    AWAITING_HAZMAT_CHECK,
    AWAITING_INSURANCE_CHECK,
    AWAITING_LABEL_PAYMENT,
    AWAITING_PACKAGE,
    AWAITING_PACKAGE_CONFIRM,
    AWAITING_PICKUP,
    AWAITING_PURCHASE_APPROVAL,
    AWAITING_SENDER,
    AWAITING_SENDER_CONFIRM,
    DONE,
    SHOWING_DETAIL,
    SHOWING_RATES,
    UNINITIALIZED,
    check_new_window_and_reset,
    get_state,
    save_state,
)
from shipping import (
    FIXED_SENDER_NAME,
    MAX_INSURABLE_VALUE_USD,
    UPS_HAZMAT_GUIDE_URL,
    UPS_PROHIBITED_URL,
    USPS_HAZMAT_GUIDE_URL,
    USPS_PROHIBITED_URL,
    Address,
    Parcel,
    PurchaseResult,
    RateOption,
    ShippoClient,
    ShippoError,
    address_diff,
    free_included_coverage_usd,
    insurance_premium_usd,
    is_domestic_country,
)

chat_proto = Protocol(spec=chat_protocol_spec)

CARD_PROTOCOL_VERSION = "1"
_PAID_WORDS = {"paid", "done", "i've paid", "ive paid", "payment done", "continue"}
_RATES_SHOWN_DEFAULT = 3


def sender_address_from_profile(profile: dict[str, Any]) -> Address:
    """Build the ship-from :class:`Address` from the user's captured profile.

    The sender is now a genuine intake step (see :func:`sender_profile_form_card`
    and :func:`_handle_sender_stage`) kept entirely separate from the recipient
    form, so it can never end up being whatever the user typed as the
    recipient's name.
    """
    return Address(
        name=str(profile["from_name"]),
        street1=str(profile["from_street1"]),
        city=str(profile["from_city"]),
        state=str(profile["from_state"]),
        zip=str(profile["from_zip"]),
        country=str(profile.get("from_country", "US")),
        phone=str(profile.get("from_phone", "")),
        email=str(profile.get("from_email", "")),
    )


def sender_profile_summary(profile: dict[str, Any]) -> str:
    """One-line confirmation of the ship-from address the user just entered."""
    addr = sender_address_from_profile(profile)
    return f"Shipping from: {addr.name}, {addr.street1}, {addr.city}, {addr.state} {addr.zip}."


def shippo_client() -> ShippoClient:
    return ShippoClient(os.environ["SHIPPO_TOKEN"])


def _wrap(card_kind: str, payload: dict[str, Any], *, is_terminal: bool = False) -> dict[str, str]:
    meta: dict[str, str] = {
        "card_protocol_version": CARD_PROTOCOL_VERSION,
        "requires_card_interaction": "true",
        "card_kind": card_kind,
        "card_payload": json.dumps(payload),
    }
    if is_terminal:
        meta["is_terminal"] = "true"
    return meta


async def send_card(ctx: Context, sender: str, narration: str, card: dict[str, str]) -> None:
    content: list[Any] = []
    if narration:
        content.append(TextContent(type="text", text=narration))
    content.append(MetadataContent(type="metadata", metadata=card))
    await ctx.send(
        sender,
        ChatMessage(timestamp=datetime.now(UTC), msg_id=uuid4(), content=content),
    )


async def send_text(ctx: Context, sender: str, text: str) -> None:
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=text)],
        ),
    )


# Carrier service names come back from Shippo with trademark glyphs (e.g. "UPS
# 2nd Day Air®"); stripped everywhere a rate is rendered to the user.
_TRADEMARK_RE = re.compile(r"[®™\u00ae\u2122]")


def _clean_name(text: str) -> str:
    return re.sub(r"\s+", " ", _TRADEMARK_RE.sub("", text or "")).strip()


def _carrier_label(rate: RateOption) -> str:
    return _clean_name(f"{rate.provider} {rate.servicelevel_name}")


def _money(amount: float, currency: str = "USD") -> str:
    if (currency or "USD").upper() == "USD":
        return f"${amount:.2f}"
    return f"{amount:.2f} {currency}"


def _eta_phrase(rate: RateOption) -> str:
    days = rate.estimated_days
    if days is None:
        return "delivery estimate not provided"
    if days <= 1:
        return "about 1 business day"
    return f"about {days} business days"


_BADGE_PHRASE = {"Recommended": "my recommendation", "Cheapest": "cheapest", "Fastest": "fastest"}


def _badges_phrase(labels: list[str]) -> str:
    """Join badge labels into natural prose (no brackets), e.g. 'cheapest and fastest'."""
    phrases = [_BADGE_PHRASE.get(label, label.lower()) for label in labels]
    if not phrases:
        return ""
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


# Non-US country signals for the "fail fast on international" check. Kept
# conservative (explicit country names / clearly non-US postal formats) so a
# normal US address is never misflagged.
_INTL_COUNTRY_RE = re.compile(
    r"\b(canada|canadian|mexico|mexican|united\s+kingdom|england|scotland|wales|"
    r"ireland|france|germany|spain|italy|netherlands|belgium|australia|"
    r"new\s+zealand|japan|china|india|brazil|switzerland|sweden|norway|denmark|"
    r"austria|portugal|poland|singapore|hong\s*kong|south\s+korea|korea|"
    r"philippines|vietnam|thailand|indonesia|malaysia|uae|dubai)\b",
    re.IGNORECASE,
)
# Canadian postal code (A1A 1A1) and UK-style outward codes — strong non-US signals.
_INTL_POSTAL_RE = re.compile(
    r"\b([A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d)\b|\b([A-Za-z]{1,2}\d[A-Za-z\d]?\s?\d[A-Za-z]{2})\b"
)


def _looks_international_text(text: str) -> bool:
    """Heuristic: does this free-text address look non-US?"""
    if not text:
        return False
    if _INTL_COUNTRY_RE.search(text):
        return True
    return bool(_INTL_POSTAL_RE.search(text))


def _looks_international_selection(selection: dict[str, Any]) -> bool:
    """Structured (form) variant: a non-US country, or a ZIP containing letters
    (US ZIPs are all digits; Canadian/UK postal codes are the giveaway)."""
    country = str(selection.get("to_country") or selection.get("from_country") or "US")
    if not is_domestic_country(country):
        return True
    zip_code = str(selection.get("to_zip") or selection.get("from_zip") or "")
    return bool(zip_code) and bool(re.search(r"[A-Za-z]", zip_code))


_INTL_MESSAGE = (
    "This demo ships US domestic only - it doesn't support international destinations, "
    "customs forms, or duties. Please enter a US shipping address to continue."
)


def _missing_sender_contact_message(profile: SenderProfile) -> str | None:
    """Catch a blank sender email/phone before Shippo does.

    Shippo's own troubleshooting docs: "Couldn't buy label. Sender info
    missing email or phone. Sender email and phone number required for
    USPS." That check only runs at label-*purchase* time - well after
    address validation, rate shopping, and (in this flow) a second Stripe
    charge have all already succeeded - so this catches it immediately
    after intake instead of after the user has paid twice.
    """
    missing = [
        label
        for label, value in (("email", profile.from_email), ("phone", profile.from_phone))
        if not (value or "").strip()
    ]
    if not missing:
        return None
    fields = " and ".join(missing)
    return (
        f"USPS requires a sender {fields} to generate the label (it's not printed on the "
        f"label - carriers use it for internal notifications only). Please re-enter your "
        f"ship-from details including your {fields}."
    )


def _preflight_selection_error(selection: dict[str, Any]) -> str | None:
    """Cheap sanity checks on the intake form's numbers before calling Shippo.

    Only runs on the form (structured) path - the prose path goes through
    Pydantic AI extraction, whose schema already enforces ``gt=0``. Returns a
    user-facing message, or ``None`` when the numbers look fine.
    """
    numeric = ("weight_lb", "length_in", "width_in", "height_in")
    if not any(k in selection for k in numeric):
        return None
    try:
        dims = {k: float(selection.get(k, 0) or 0) for k in numeric}
        declared = float(selection.get("declared_value_usd", 0) or 0)
    except (TypeError, ValueError):
        return "Weight and dimensions need to be numbers - please re-enter them."
    if [k for k, v in dims.items() if v <= 0]:
        return "Weight and every dimension must be greater than zero - please re-enter them."
    if declared < 0:
        return "Declared value can't be negative - please re-enter it."
    if declared > MAX_INSURABLE_VALUE_USD:
        return (
            f"That declared value looks unusually high. This demo caps it at "
            f"{_money(MAX_INSURABLE_VALUE_USD)} (the most XCover will insure) - "
            "please re-enter a lower value."
        )
    return None


# There is intentionally no payment card here. The payment gate uses the
# native uagents_core payment protocol (see :mod:`payment`) so ASI:One renders
# its own "Pay with Stripe / Reject" sheet, exactly like the quiz-agent.


def sender_profile_form_card() -> dict[str, str]:
    # The documented `form` schema is exactly {title, fields, submit_cta} - unlike
    # `carousel`, it has no top-level "subtitle" key. A mismatched payload gets
    # silently rejected by ASI:One and falls back to plain text, so any framing
    # copy belongs in the narration text passed by callers, not here.
    payload = {
        "title": "Your shipping profile",
        "fields": [
            {
                "name": "from_name",
                "kind": "text",
                "label": "Your name",
                "required": True,
                "placeholder": FIXED_SENDER_NAME,
            },
            {
                "name": "from_street1",
                "kind": "text",
                "label": "Street address",
                "required": True,
                "placeholder": "215 Clayton St.",
            },
            {
                "name": "from_city",
                "kind": "text",
                "label": "City",
                "required": True,
                "placeholder": "San Francisco",
            },
            {
                "name": "from_state",
                "kind": "text",
                "label": "State (2-letter)",
                "required": True,
                "placeholder": "CA",
            },
            {
                "name": "from_zip",
                "kind": "text",
                "label": "ZIP code",
                "required": True,
                "placeholder": "94117",
            },
            # USPS (and some other carriers) reject the label *purchase* call - not
            # the earlier rate-shop call - if the sender's phone/email are blank,
            # per Shippo's own troubleshooting doc ("Sender email and phone number
            # required for USPS"). That only surfaces after the second payment has
            # already cleared, so both are required here instead of optional.
            {
                "name": "from_phone",
                "kind": "text",
                "label": "Phone",
                "required": True,
                "placeholder": "+1 555 341 9393",
            },
            {
                "name": "from_email",
                "kind": "text",
                "label": "Email",
                "required": True,
                "placeholder": "shawn@example.com",
            },
        ],
        "submit_cta": {"label": "Continue", "selection": {"action": "submit_sender"}},
    }
    return _wrap("form", payload)


def package_form_card() -> dict[str, str]:
    payload = {
        "title": "Package details",
        "fields": [
            {"name": "to_name", "kind": "text", "label": "Recipient name", "required": True},
            {"name": "to_street1", "kind": "text", "label": "Street address", "required": True},
            {"name": "to_city", "kind": "text", "label": "City", "required": True},
            {"name": "to_state", "kind": "text", "label": "State (2-letter)", "required": True},
            {"name": "to_zip", "kind": "text", "label": "ZIP code", "required": True},
            {"name": "weight_lb", "kind": "number", "label": "Weight (lb)", "required": True},
            {"name": "length_in", "kind": "number", "label": "Length (in)", "required": True},
            {"name": "width_in", "kind": "number", "label": "Width (in)", "required": True},
            {"name": "height_in", "kind": "number", "label": "Height (in)", "required": True},
            {
                "name": "declared_value_usd",
                "kind": "number",
                "label": "Declared value (USD)",
                "required": False,
                "placeholder": "0",
            },
        ],
        "submit_cta": {"label": "Get rates", "selection": {"action": "submit_package"}},
    }
    return _wrap("form", payload)


def _format_address_line(addr: Address) -> str:
    return f"{addr.street1}, {addr.city}, {addr.state} {addr.zip}".strip(", ")


def _correction_hint(submitted: Address, corrected: Address | None) -> str:
    """A short ' Did you mean: ...?' suffix when Shippo suggests a different
    address than what was typed - used on the *invalid* path, where we still
    make the user re-enter the form but want to point them at the likely fix
    (e.g. a street Shippo couldn't match at all, per its own docs example).
    """
    if not corrected or not address_diff(submitted, corrected):
        return ""
    return f" Did you mean: {_format_address_line(corrected)}?"


def address_correction_card(submitted: Address, corrected: Address) -> dict[str, str]:
    """A ``review`` card offering Shippo's suggested correction vs. what the
    user typed - covers the "valid, but probably not what you meant" case
    (e.g. a city that doesn't match its own ZIP) that address validation
    alone doesn't catch, since Shippo's own validator considers it
    deliverable either way.
    """
    payload = {
        "title": "Double-check this address",
        "summary_rows": [
            {"label": "You entered", "value": _format_address_line(submitted)},
            {"label": "Suggested (USPS-verified)", "value": _format_address_line(corrected)},
        ],
        "approve_cta": {
            "label": "Use suggested address",
            "primary": True,
            "selection": {"action": "use_suggested_address"},
        },
        "reject_cta": {
            "label": "Keep as I typed it",
            "selection": {"action": "keep_typed_address"},
        },
    }
    return _wrap("review", payload)


_BADGE_VARIANT = {"Recommended": "success", "Cheapest": "success", "Fastest": "info"}


def _rate_badge_labels(rate: RateOption, tags: dict[str, str]) -> list[str]:
    """Which of cheapest/fastest/recommended apply to this rate, as plain labels."""
    labels: list[str] = []
    if tags.get("recommended") == rate.rate_id:
        labels.append("Recommended")
    if tags.get("cheapest") == rate.rate_id:
        labels.append("Cheapest")
    if tags.get("fastest") == rate.rate_id:
        labels.append("Fastest")
    return labels


def _rate_badges_cta(rate: RateOption, tags: dict[str, str]) -> list[dict[str, str]]:
    """Badges in the shape the carousel schema expects: ``{label, variant}``."""
    return [
        {"label": label, "variant": _BADGE_VARIANT.get(label, "info")}
        for label in _rate_badge_labels(rate, tags)
    ]


def _curate_rates(
    rates: list[RateOption], tags: dict[str, str], *, limit: int = _RATES_SHOWN_DEFAULT
) -> list[RateOption]:
    """The short, curated set to show by default: recommended, cheapest, fastest.

    Deduplicated (a rate can be more than one of these) and capped at ``limit``.
    The user can always ask to "show all" to see every option Shippo returned.
    """
    by_id = {r.rate_id: r for r in rates}
    picked_ids: list[str] = []
    for key in ("recommended", "cheapest", "fastest"):
        rid = tags.get(key)
        if rid and rid not in picked_ids and rid in by_id:
            picked_ids.append(rid)
    curated = [by_id[rid] for rid in picked_ids]
    return curated[:limit] if limit else curated


def rates_carousel(
    rates: list[RateOption], tags: dict[str, str], *, total: int | None = None
) -> dict[str, str]:
    """Build the rate-shopping carousel.

    ``total`` is the full count of rates Shippo returned. When it's larger than
    ``len(rates)`` (i.e. this is the curated subset), a real tappable "See all"
    tile is appended so the full list is discoverable without needing to type
    anything, instead of only being reachable via a text hint.
    """
    items: list[dict[str, Any]] = []
    for r in rates:
        item: dict[str, Any] = {
            "id": r.rate_id,
            "title": _carrier_label(r),
            "subtitle": _eta_phrase(r).capitalize(),
            "secondary_text": _money(r.amount, r.currency),
            "primary_cta": {
                "label": f"Buy for {_money(r.amount, r.currency)}",
                "selection": {"action": "select_rate", "rate_id": r.rate_id},
            },
        }
        badges = _rate_badges_cta(r, tags)
        if badges:
            item["badges"] = badges
        items.append(item)
    if total is not None and total > len(rates):
        items.append(
            {
                "id": "show_all_rates",
                "title": f"See all {total} options",
                "subtitle": f"{total - len(rates)} more not shown here",
                "primary_cta": {
                    "label": "Show all",
                    "selection": {"action": "show_all_rates"},
                },
            }
        )
    return _wrap(
        "carousel",
        {
            "title": "Choose a shipping option",
            "subtitle": "Test-mode rates from Shippo",
            "items": items,
        },
    )


def rates_text_summary(shown: list[RateOption], tags: dict[str, str], *, total: int) -> str:
    """Guaranteed-visible plain-text narration alongside the carousel card.

    Because ASI:One silently degrades to plain text on any card-schema mismatch,
    this narration is a complete, self-contained rate comparison the user can act
    on even if the carousel never renders.
    """
    curated = len(shown) < total
    if curated:
        header = f"I found {total} shipping options. Here are the {len(shown)} that stand out:"
    elif total == 1:
        header = "I found one shipping option for this package:"
    else:
        header = f"Here are all {total} shipping options:"
    lines = [header, ""]
    for i, r in enumerate(shown, start=1):
        line = f"{i}. {_carrier_label(r)}: {_money(r.amount, r.currency)}, {_eta_phrase(r)}"
        badges = _badges_phrase(_rate_badge_labels(r, tags))
        if badges:
            line += f" — {badges}"
        lines.append(line)
    lines.append("")
    if curated:
        remaining = total - len(shown)
        lines.append(
            f"Tap a card to choose one, or reply with a number or carrier name. "
            f"Want the other {remaining}? Just say 'show all'."
        )
    else:
        lines.append("Tap a card to choose one, or reply with a number or carrier name.")
    return "\n".join(lines)


def rate_detail_card(rate: RateOption) -> dict[str, str]:
    summary_rows = [
        {"label": "Carrier", "value": rate.provider},
        {
            "label": "Service",
            "value": _clean_name(rate.servicelevel_name or rate.servicelevel_token),
        },
        {"label": "Price", "value": _money(rate.amount, rate.currency)},
        {"label": "Estimated transit", "value": _eta_phrase(rate)},
    ]
    if rate.duration_terms:
        summary_rows.append({"label": "Terms", "value": rate.duration_terms})
    payload = {
        "title": _carrier_label(rate),
        "summary_rows": summary_rows,
        "ctas": [
            {
                "label": "Continue to purchase",
                "primary": True,
                "selection": {"action": "buy_rate", "rate_id": rate.rate_id},
            },
            {"label": "Back to options", "selection": {"action": "back_to_rates"}},
        ],
    }
    return _wrap("detail", payload)


def purchase_review_card(rate: RateOption) -> dict[str, str]:
    summary_rows = [
        {"label": "Carrier", "value": _carrier_label(rate)},
        {"label": "Total", "value": _money(rate.amount, rate.currency)},
    ]
    if rate.included_insurance_price > 0:
        summary_rows.insert(
            1, {"label": "Insurance", "value": _money(rate.included_insurance_price, rate.currency)}
        )
    payload = {
        "title": "Confirm and buy label",
        "summary_rows": summary_rows,
        "approve_cta": {
            "label": f"Confirm and pay {_money(rate.amount, rate.currency)}",
            "primary": True,
            "selection": {"action": "approve_purchase"},
        },
        "reject_cta": {"label": "Cancel", "selection": {"action": "deny_purchase"}},
    }
    return _wrap("review", payload)


def _prohibited_url(provider: str) -> str:
    """The carrier-specific prohibited-items page for the chosen provider."""
    return UPS_PROHIBITED_URL if (provider or "").strip().upper() == "UPS" else USPS_PROHIBITED_URL


def hazmat_review_card(provider: str) -> dict[str, str]:
    """Self-certification gate shown before purchase.

    The buttons state the *outcome* ("Nothing hazardous, continue" vs. "This
    needs special handling") rather than a raw yes/no, since it's easy to
    misread whether "yes" means "yes it's hazardous" or "yes, continue".
    """
    payload = {
        "title": "Confirm what's inside",
        "summary_rows": [
            {
                "label": "Prohibited items",
                "value": f"Review {provider}'s restricted/prohibited list before continuing.",
            },
            {
                "label": "Your responsibility",
                "value": "Declaring contents accurately is the shipper's responsibility.",
            },
        ],
        "approve_cta": {
            "label": "Nothing hazardous, continue",
            "primary": True,
            "selection": {"action": "hazmat_clear"},
        },
        "reject_cta": {
            "label": "This needs special handling",
            "selection": {"action": "hazmat_stop"},
        },
    }
    return _wrap("review", payload)


def insurance_review_card(
    rate: RateOption, *, free_coverage: float, declared_value: float, premium: float
) -> dict[str, str]:
    """Optional-insurance offer, shown only when declared value exceeds the
    coverage the chosen service already includes for free."""
    payload = {
        "title": "Add shipping insurance?",
        "summary_rows": [
            {
                "label": "Included free",
                "value": f"{_money(free_coverage)} with {_carrier_label(rate)}",
            },
            {"label": "Your declared value", "value": _money(declared_value)},
            {
                "label": "Full coverage",
                "value": f"insure {_money(declared_value)} for about {_money(premium)} more",
            },
        ],
        "approve_cta": {
            "label": f"Add insurance for about {_money(premium)}",
            "primary": True,
            "selection": {"action": "add_insurance"},
        },
        "reject_cta": {"label": "Skip insurance", "selection": {"action": "skip_insurance"}},
    }
    return _wrap("review", payload)


def pickup_form_card(provider: str) -> dict[str, str]:
    payload = {
        "title": f"Schedule a {provider} pickup",
        "fields": [
            {
                "name": "building_location_type",
                "kind": "select",
                "label": "Where will the parcel be?",
                "required": True,
                "options": [
                    {"value": "Front Door", "label": "Front Door"},
                    {"value": "Back Door", "label": "Back Door"},
                    {"value": "Office", "label": "Office"},
                    {"value": "Reception", "label": "Reception"},
                    {"value": "Mail Room", "label": "Mail Room"},
                ],
            },
            {
                "name": "instructions",
                "kind": "text",
                "label": "Instructions for the courier (optional)",
                "required": False,
                "placeholder": "e.g. Ring the bell",
            },
        ],
        "submit_cta": {"label": "Schedule pickup", "selection": {"action": "schedule_pickup"}},
    }
    return _wrap("form", payload)


def confirmation_card(purchase: PurchaseResult, rate: RateOption | None = None) -> dict[str, str]:
    """The one terminal card of the flow — carries the single TEST/SAMPLE note.

    ``rate`` is the exact :class:`RateOption` the user picked earlier in this
    same conversation, used to fill in the carrier when Shippo's transaction
    response doesn't expand it (see ``ShippoClient.purchase``'s docstring) so
    this card never shows a blank/unknown carrier.
    """
    carrier = _carrier_label(rate) if rate else purchase.provider
    payload = {
        "title": "Label ready",
        "summary_rows": [
            {"label": "Carrier", "value": carrier or "n/a"},
            {"label": "Tracking number", "value": purchase.tracking_number or "n/a"},
            {"label": "Mode", "value": "TEST / SAMPLE - not a real shipment"},
        ],
        "ctas": [{"label": "Done", "selection": {"action": "done"}}],
    }
    return _wrap("detail", payload, is_terminal=True)


def _extract_text(msg: ChatMessage) -> str:
    for block in msg.content:
        if isinstance(block, TextContent):
            text = re.sub(r"^@\S+\s+", "", (block.text or "")).strip()
            text = re.sub(r"\n*!\[[^\]]*\]\(https?://[^)]+\)", "", text).strip()
            return text
    return ""


_ACTION_KEYWORDS = [
    ("show_all_rates", r"show\s*all|see\s*all|all\s*options|more\s*options|full\s*list"),
    (
        "use_suggested_address",
        r"use\s*(the\s*)?suggest|suggested\s*(one|address)|yes.{0,10}suggest",
    ),
    (
        "keep_typed_address",
        (
            r"keep\s*(it\s*)?as\s*(i\s*)?typed|keep\s*(it\s*)?as\s*is|keep\s*mine|"
            r"keep\s*(the\s*)?original|as\s*typed"
        ),
    ),
    ("approve_purchase", r"\b(confirm|approve|buy|purchase)\b"),
    ("deny_purchase", r"\b(cancel|deny|reject|no)\b"),
    ("reject_payment", r"reject\s*payment"),
    ("back_to_rates", r"back"),
    ("schedule_pickup", r"pickup|pick\s*up|schedule"),
    ("done", r"\b(done|finish|thanks|thank you)\b"),
]


def parse_selection(text: str) -> dict[str, Any]:
    """Parse a card selection from JSON (direct @mention) or prose (planner)."""
    stripped = (text or "").strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                return {str(k): v for k, v in data.items()}
        except json.JSONDecodeError:
            pass

    selection: dict[str, Any] = {}
    m = re.search(r"rate[_\s-]?id[\s:=\"']*([A-Za-z0-9]+)", stripped, re.IGNORECASE)
    if m:
        selection["rate_id"] = m.group(1)
        selection.setdefault("action", "select_rate")
    low = stripped.lower()
    for action, pattern in _ACTION_KEYWORDS:
        if re.search(pattern, low):
            selection.setdefault("action", action)
            break
    return selection


def _sender_from_selection(selection: dict[str, Any]) -> SenderProfile | None:
    """Build :class:`SenderProfile` from a submitted form selection (JSON)."""
    try:
        return SenderProfile(
            from_name=str(selection["from_name"]),
            from_street1=str(selection["from_street1"]),
            from_city=str(selection["from_city"]),
            from_state=str(selection["from_state"]),
            from_zip=str(selection["from_zip"]),
            from_country=str(selection.get("from_country", "US")),
            from_phone=str(selection.get("from_phone", "") or ""),
            from_email=str(selection.get("from_email", "") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _package_from_selection(selection: dict[str, Any]) -> PackageDetails | None:
    """Build :class:`PackageDetails` from a submitted form selection (JSON)."""
    try:
        return PackageDetails(
            to_name=str(selection["to_name"]),
            to_street1=str(selection["to_street1"]),
            to_city=str(selection["to_city"]),
            to_state=str(selection["to_state"]),
            to_zip=str(selection["to_zip"]),
            to_country=str(selection.get("to_country", "US")),
            weight_lb=float(selection["weight_lb"]),
            length_in=float(selection["length_in"]),
            width_in=float(selection["width_in"]),
            height_in=float(selection["height_in"]),
            declared_value_usd=float(selection.get("declared_value_usd", 0) or 0),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _to_address(pkg: PackageDetails) -> Address:
    return Address(
        name=pkg.to_name,
        street1=pkg.to_street1,
        city=pkg.to_city,
        state=pkg.to_state,
        zip=pkg.to_zip,
        country=pkg.to_country,
    )


def _parcel(pkg: PackageDetails) -> Parcel:
    return Parcel(
        length_in=pkg.length_in,
        width_in=pkg.width_in,
        height_in=pkg.height_in,
        weight_lb=pkg.weight_lb,
    )


def _tag_rates(rates: list[RateOption]) -> dict[str, str]:
    if not rates:
        return {}
    cheapest = min(rates, key=lambda r: r.amount)
    with_eta = [r for r in rates if r.estimated_days is not None]
    fastest = min(with_eta, key=lambda r: r.estimated_days or 0) if with_eta else cheapest
    # Recommend the cheapest option that is also within a day of the fastest ETA.
    if fastest.estimated_days is not None:
        contenders = [
            r
            for r in rates
            if r.estimated_days is not None and r.estimated_days <= fastest.estimated_days + 1
        ]
        recommended = min(contenders, key=lambda r: r.amount) if contenders else cheapest
    else:
        recommended = cheapest
    return {
        "cheapest": cheapest.rate_id,
        "fastest": fastest.rate_id,
        "recommended": recommended.rate_id,
    }


def _find_rate(rates: list[dict[str, Any]], rate_id: str) -> RateOption | None:
    for r in rates:
        if r.get("rate_id") == rate_id:
            return RateOption(**r)
    return None


def _resolve_selected_rate(
    rates: list[dict[str, Any]], text: str, selection: dict[str, Any]
) -> RateOption | None:
    """Resolve which carousel option the user picked.

    Prefers the exact ``rate_id`` from a tapped CTA (JSON selection), then falls
    back to prose the way a chat user would phrase it: a tag word
    ("cheapest"/"fastest"/"recommended"), a 1-based number, or a carrier name.
    """
    rate_id = selection.get("rate_id")
    if rate_id:
        found = _find_rate(rates, str(rate_id))
        if found:
            return found

    if not rates:
        return None
    rate_objs = [RateOption(**r) for r in rates]
    tags = _tag_rates(rate_objs)
    low = (text or "").lower()

    for word, key in (
        ("cheapest", "cheapest"),
        ("fastest", "fastest"),
        ("recommend", "recommended"),
    ):
        if word in low and tags.get(key):
            match = _find_rate(rates, tags[key])
            if match:
                return match

    num = re.search(r"\bnumber\s+(\d+)\b|#\s*(\d+)|^\s*(\d+)\s*$", low)
    if num:
        digits = next((g for g in num.groups() if g), None)
        if digits is not None:
            idx = int(digits) - 1
            if 0 <= idx < len(rate_objs):
                return rate_objs[idx]

    for r in rate_objs:
        if r.provider and r.provider.lower() in low:
            return r
    return None


async def _deliver_label(ctx: Context, sender: str, purchase: PurchaseResult) -> None:
    """Send the label PDF link.

    Shippo's test-mode ``label_url`` is already a fully public, directly
    downloadable PDF - re-uploading it to Agentverse ExternalStorage and
    attaching it as ``ResourceContent`` added an extra hop that produced a
    broken, unlabeled duplicate link in the chat with no upside, so we just
    link straight to it. The single TEST/SAMPLE disclaimer lives on the
    confirmation card/message that follows, not here.
    """
    if purchase.label_url:
        await send_text(ctx, sender, f"[Download your shipping label (PDF)]({purchase.label_url})")
    else:
        await send_text(
            ctx,
            sender,
            "The label was purchased, but Shippo didn't return a label URL - check your "
            "Shippo dashboard for it.",
        )


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id),
    )
    try:
        await _handle_inner(ctx, sender, msg)
    except Exception as exc:
        ctx.logger.exception("[shipping] handler crashed")
        await send_text(ctx, sender, f"Something went wrong on my end ({exc}). Please try again.")


async def _handle_inner(ctx: Context, sender: str, msg: ChatMessage) -> None:
    text = _extract_text(msg)
    # New chat window -> full reset, so a new conversation always starts unpaid
    # (see check_new_window_and_reset's docstring for why this is necessary).
    check_new_window_and_reset(ctx, sender)
    state_data = get_state(ctx, sender)
    selection = parse_selection(text)

    # RULE 1: the payment gate fires on the very first message, no exceptions.
    # This sends a bare native RequestPayment - no narration, no custom card -
    # so ASI:One renders its own payment sheet (mirrors the quiz-agent exactly).
    if state_data["state"] == UNINITIALIZED:
        await payment.request_payment(ctx, sender, state_data)
        return

    if not state_data.get("stripe_paid"):
        if text.lower() in _PAID_WORDS:
            if await payment.confirm_payment_via_text(ctx, sender):
                return
            await send_text(
                ctx,
                sender,
                "Stripe still shows this as unpaid. Finish the checkout, then type 'paid' again.",
            )
            return
        # Any other message while unpaid -> re-issue the native payment request.
        await payment.request_payment(ctx, sender, state_data)
        return

    stage = state_data["state"]
    if stage == AWAITING_SENDER:
        await _handle_sender_stage(ctx, sender, state_data, text, selection)
    elif stage == AWAITING_SENDER_CONFIRM:
        await _handle_sender_confirm_stage(ctx, sender, state_data, selection)
    elif stage == AWAITING_PACKAGE:
        await _handle_package_stage(ctx, sender, state_data, text, selection)
    elif stage == AWAITING_PACKAGE_CONFIRM:
        await _handle_package_confirm_stage(ctx, sender, state_data, selection)
    elif stage == SHOWING_RATES:
        await _handle_rates_stage(ctx, sender, state_data, text, selection)
    elif stage == SHOWING_DETAIL:
        await _handle_detail_stage(ctx, sender, state_data, selection)
    elif stage == AWAITING_HAZMAT_CHECK:
        await _handle_hazmat_stage(ctx, sender, state_data, text, selection)
    elif stage == AWAITING_INSURANCE_CHECK:
        await _handle_insurance_stage(ctx, sender, state_data, text, selection)
    elif stage == AWAITING_PURCHASE_APPROVAL:
        await _handle_approval_stage(ctx, sender, state_data, selection)
    elif stage == AWAITING_LABEL_PAYMENT:
        await _handle_label_payment_stage(ctx, sender, state_data, text)
    elif stage == AWAITING_PICKUP:
        await _handle_pickup_stage(ctx, sender, state_data, selection)
    else:  # DONE or anything else -> start a new package intake within the paid session.
        state_data["state"] = AWAITING_PACKAGE
        save_state(ctx, sender, state_data)
        await send_card(
            ctx, sender, "Let's ship another package. Enter its details:", package_form_card()
        )


async def _handle_sender_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], text: str, selection: dict[str, Any]
) -> None:
    if _looks_international_text(text) or _looks_international_selection(selection):
        await send_card(ctx, sender, _INTL_MESSAGE, sender_profile_form_card())
        return

    profile = _sender_from_selection(selection)
    if profile is None and text:
        # Prose path: use Pydantic AI structured extraction, same pattern as intake.
        try:
            profile = await extract_sender_profile(text)
        except Exception as exc:  # noqa: BLE001
            ctx.logger.warning(f"[sender] extraction failed: {exc}")
            profile = None
    if profile is None:
        await send_card(
            ctx,
            sender,
            "I need your ship-from address to continue - please fill in the form.",
            sender_profile_form_card(),
        )
        return

    contact_error = _missing_sender_contact_message(profile)
    if contact_error:
        await send_card(ctx, sender, contact_error, sender_profile_form_card())
        return

    from_addr = sender_address_from_profile(profile.model_dump())
    try:
        validation = await asyncio.to_thread(shippo_client().validate_address, from_addr)
    except ShippoError as exc:
        # Fail open: a Shippo outage shouldn't dead-end the whole demo. The
        # user still typed a complete address; we just couldn't double-check
        # it, so say so and move on rather than blocking on our own error.
        ctx.logger.warning(f"[sender] address validation errored: {exc}")
        await _accept_sender_profile(ctx, sender, state_data, profile)
        return

    if not validation.is_valid:
        problems = "; ".join(validation.messages) or "the address could not be verified"
        hint = _correction_hint(from_addr, validation.corrected)
        await send_card(
            ctx,
            sender,
            f"That ship-from address needs a fix: {problems}.{hint} Please re-enter it.",
            sender_profile_form_card(),
        )
        return

    if validation.corrected and address_diff(from_addr, validation.corrected):
        state_data["pending_sender_typed"] = profile.model_dump()
        state_data["pending_sender_corrected"] = validation.corrected.model_dump()
        state_data["state"] = AWAITING_SENDER_CONFIRM
        save_state(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            "That address is deliverable, but USPS has a slightly different version on "
            "file - which one should the label use?",
            address_correction_card(from_addr, validation.corrected),
        )
        return

    await _accept_sender_profile(ctx, sender, state_data, profile)


async def _accept_sender_profile(
    ctx: Context, sender: str, state_data: dict[str, Any], profile: SenderProfile
) -> None:
    """Save the (validated, or validation-unavailable) sender profile and move
    on to package intake - the one path shared by "address matched exactly"
    and "Shippo's validator was unreachable" outcomes."""
    state_data["sender_profile"] = profile.model_dump()
    state_data.pop("pending_sender_typed", None)
    state_data.pop("pending_sender_corrected", None)
    state_data["state"] = AWAITING_PACKAGE
    save_state(ctx, sender, state_data)
    await send_card(
        ctx,
        sender,
        f"{sender_profile_summary(state_data['sender_profile'])} Now tell me about your package.",
        package_form_card(),
    )


async def _handle_sender_confirm_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], selection: dict[str, Any]
) -> None:
    """Resolve the "use suggested / keep as typed" choice from
    :func:`address_correction_card` for the ship-from address."""
    typed = state_data.get("pending_sender_typed")
    corrected = state_data.get("pending_sender_corrected")
    if not typed:
        state_data["state"] = AWAITING_SENDER
        save_state(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            "Let's start over - where are you shipping from?",
            sender_profile_form_card(),
        )
        return

    action = selection.get("action")
    if action not in {"use_suggested_address", "keep_typed_address"}:
        submitted = sender_address_from_profile(typed)
        suggested = Address(**corrected) if corrected else submitted
        await send_card(
            ctx,
            sender,
            "Tap a button above, or reply 'use suggested' or 'keep as typed'.",
            address_correction_card(submitted, suggested),
        )
        return

    profile_dict = dict(typed)
    if action == "use_suggested_address" and corrected:
        profile_dict["from_street1"] = corrected.get("street1", profile_dict["from_street1"])
        profile_dict["from_city"] = corrected.get("city", profile_dict["from_city"])
        profile_dict["from_state"] = corrected.get("state", profile_dict["from_state"])
        profile_dict["from_zip"] = corrected.get("zip", profile_dict["from_zip"])

    await _accept_sender_profile(ctx, sender, state_data, SenderProfile(**profile_dict))


async def _handle_package_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], text: str, selection: dict[str, Any]
) -> None:
    if not state_data.get("sender_profile"):
        # Defensive: a session persisted before the sender-profile step existed
        # (or that otherwise skipped it) must not crash on a missing sender -
        # send it back to capture one instead.
        state_data["state"] = AWAITING_SENDER
        save_state(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            "First, where are you shipping from?",
            sender_profile_form_card(),
        )
        return

    if _looks_international_text(text) or _looks_international_selection(selection):
        await send_card(ctx, sender, _INTL_MESSAGE, package_form_card())
        return

    preflight = _preflight_selection_error(selection)
    if preflight:
        await send_card(ctx, sender, preflight, package_form_card())
        return

    pkg = _package_from_selection(selection)
    if pkg is None and text:
        # Prose path: use Pydantic AI structured extraction.
        try:
            pkg = await extract_package(text)
        except Exception as exc:  # noqa: BLE001
            ctx.logger.warning(f"[intake] extraction failed: {exc}")
            pkg = None
    if pkg is None:
        await send_card(
            ctx,
            sender,
            "I need the full package details to continue - please fill in the form.",
            package_form_card(),
        )
        return

    to_addr = _to_address(pkg)
    try:
        validation = await asyncio.to_thread(shippo_client().validate_address, to_addr)
    except ShippoError as exc:
        # Fail open here too - see the matching comment in _handle_sender_stage.
        ctx.logger.warning(f"[intake] address validation errored: {exc}")
        await _run_rate_shop(ctx, sender, state_data, pkg)
        return

    if not validation.is_valid:
        problems = "; ".join(validation.messages) or "the address could not be verified"
        hint = _correction_hint(to_addr, validation.corrected)
        await send_card(
            ctx,
            sender,
            f"That destination address needs a fix: {problems}.{hint} Please re-enter it.",
            package_form_card(),
        )
        return

    if validation.corrected and address_diff(to_addr, validation.corrected):
        state_data["pending_package_typed"] = pkg.model_dump()
        state_data["pending_package_corrected"] = validation.corrected.model_dump()
        state_data["state"] = AWAITING_PACKAGE_CONFIRM
        save_state(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            "That address is deliverable, but USPS has a slightly different version on "
            "file - which one should the label use?",
            address_correction_card(to_addr, validation.corrected),
        )
        return

    await _run_rate_shop(ctx, sender, state_data, pkg)


async def _run_rate_shop(
    ctx: Context, sender: str, state_data: dict[str, Any], pkg: PackageDetails
) -> None:
    """Shared tail of package intake: rate-shop and show the curated carousel.

    Reached either straight from a package address that validated cleanly, or
    from :func:`_handle_package_confirm_stage` once the user has picked
    "suggested" or "as typed" for a corrected destination address.
    """
    client = shippo_client()
    from_addr = sender_address_from_profile(state_data["sender_profile"])
    to_addr = _to_address(pkg)
    rates = await asyncio.to_thread(client.rate_shop, from_addr, to_addr, _parcel(pkg))
    if not rates:
        state_data["state"] = AWAITING_PACKAGE
        state_data.pop("pending_package_typed", None)
        state_data.pop("pending_package_corrected", None)
        save_state(ctx, sender, state_data)
        await send_text(
            ctx,
            sender,
            "No carrier returned a rate for this package in test mode. That usually means "
            "it's over a carrier's size or weight limit (commonly around 150 lb, or too "
            "large in length plus girth), or no connected test carrier serves that route. "
            "Try reducing the weight or dimensions, or double-check the destination, then "
            "send the form again.",
        )
        return

    tags = _tag_rates(rates)
    state_data["package"] = pkg.model_dump()
    state_data["rates"] = [r.model_dump() for r in rates]
    state_data["selected_rate_id"] = None
    state_data.pop("pending_package_typed", None)
    state_data.pop("pending_package_corrected", None)
    state_data["state"] = SHOWING_RATES
    save_state(ctx, sender, state_data)

    curated = _curate_rates(rates, tags)
    # A short, heavy/oversized package legitimately gets only one or two rates;
    # say why instead of showing an unexplained tiny list.
    caveat = ""
    if len(rates) <= 2:
        caveat = (
            "Only a few carriers returned a rate for this package - larger or heavier "
            "parcels are served by fewer services. Here's what's available:\n\n"
        )
    await send_card(
        ctx,
        sender,
        caveat + rates_text_summary(curated, tags, total=len(rates)),
        rates_carousel(curated, tags, total=len(rates)),
    )


async def _handle_package_confirm_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], selection: dict[str, Any]
) -> None:
    """Resolve the "use suggested / keep as typed" choice from
    :func:`address_correction_card` for the recipient address."""
    typed = state_data.get("pending_package_typed")
    corrected = state_data.get("pending_package_corrected")
    if not typed:
        state_data["state"] = AWAITING_PACKAGE
        save_state(ctx, sender, state_data)
        await send_card(
            ctx, sender, "Let's try that again - the package details:", package_form_card()
        )
        return

    action = selection.get("action")
    if action not in {"use_suggested_address", "keep_typed_address"}:
        submitted = _to_address(PackageDetails(**typed))
        suggested = Address(**corrected) if corrected else submitted
        await send_card(
            ctx,
            sender,
            "Tap a button above, or reply 'use suggested' or 'keep as typed'.",
            address_correction_card(submitted, suggested),
        )
        return

    pkg_dict = dict(typed)
    if action == "use_suggested_address" and corrected:
        pkg_dict["to_street1"] = corrected.get("street1", pkg_dict["to_street1"])
        pkg_dict["to_city"] = corrected.get("city", pkg_dict["to_city"])
        pkg_dict["to_state"] = corrected.get("state", pkg_dict["to_state"])
        pkg_dict["to_zip"] = corrected.get("zip", pkg_dict["to_zip"])

    await _run_rate_shop(ctx, sender, state_data, PackageDetails(**pkg_dict))


async def _handle_rates_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], text: str, selection: dict[str, Any]
) -> None:
    rates_raw = state_data.get("rates", [])
    if selection.get("action") == "show_all_rates":
        rate_objs = [RateOption(**r) for r in rates_raw]
        tags = _tag_rates(rate_objs)
        await send_card(
            ctx,
            sender,
            rates_text_summary(rate_objs, tags, total=len(rate_objs)),
            rates_carousel(rate_objs, tags),
        )
        return

    rate = _resolve_selected_rate(rates_raw, text, selection)
    if not rate:
        await send_text(
            ctx,
            sender,
            "I couldn't tell which option you picked - tap a card above, or reply with its "
            "number, the carrier name, 'cheapest', 'fastest', 'recommended', or 'show all'.",
        )
        return
    state_data["selected_rate_id"] = rate.rate_id
    state_data["state"] = SHOWING_DETAIL
    save_state(ctx, sender, state_data)
    detail_lines = [
        f"{_carrier_label(rate)}: {_money(rate.amount, rate.currency)}, {_eta_phrase(rate)}.",
    ]
    if rate.duration_terms:
        detail_lines.append(f"Terms: {rate.duration_terms}")
    detail_lines.append("")
    detail_lines.append("Reply 'buy' to continue to purchase, or 'back' to see the other options.")
    await send_card(ctx, sender, "\n".join(detail_lines), rate_detail_card(rate))


async def _handle_detail_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], selection: dict[str, Any]
) -> None:
    action = selection.get("action")
    rates = state_data.get("rates", [])
    if action == "back_to_rates":
        state_data["state"] = SHOWING_RATES
        save_state(ctx, sender, state_data)
        rate_objs = [RateOption(**r) for r in rates]
        rate_tags = _tag_rates(rate_objs)
        curated = _curate_rates(rate_objs, rate_tags)
        await send_card(
            ctx,
            sender,
            rates_text_summary(curated, rate_tags, total=len(rate_objs)),
            rates_carousel(curated, rate_tags, total=len(rate_objs)),
        )
        return

    rate_id = selection.get("rate_id") or state_data.get("selected_rate_id")
    rate = _find_rate(rates, str(rate_id)) if rate_id else None
    if not rate:
        await send_text(ctx, sender, "Pick an option first, then continue to purchase.")
        return

    # Before purchase: self-certification of contents (hazmat), then optional
    # insurance. Both fire between "Continue to purchase" and the approval
    # gate, per shipment (contents/value are per-package, not a session setting).
    state_data["selected_rate_id"] = rate.rate_id
    state_data["state"] = AWAITING_HAZMAT_CHECK
    save_state(ctx, sender, state_data)
    await _send_hazmat_gate(ctx, sender, rate)


async def _send_hazmat_gate(ctx: Context, sender: str, rate: RateOption) -> None:
    prohibited = _prohibited_url(rate.provider)
    narration = (
        f"Before I buy this label, please confirm what's inside. Prohibited and "
        f"restricted items can't be shipped - here is {rate.provider}'s list: {prohibited}\n\n"
        "Declaring the contents accurately is the shipper's responsibility."
    )
    await send_card(ctx, sender, narration, hazmat_review_card(rate.provider))


def _hazmat_signal(text: str, selection: dict[str, Any]) -> str | None:
    """Interpret the hazmat card response from a JSON action or prose.

    Returns ``"clear"``, ``"stop"``, or ``None`` (ambiguous -> re-prompt). We
    read the raw text ourselves rather than the generic parse, since a bare
    "no" is genuinely ambiguous here and must not be silently assumed.
    """
    action = selection.get("action")
    if action == "hazmat_clear":
        return "clear"
    if action == "hazmat_stop":
        return "stop"
    low = (text or "").lower()
    if re.search(r"special\s*handling|hazardous|hazmat|prohibited|restricted|dangerous", low):
        return "stop"
    if re.search(r"nothing\s*hazardous|not\s*hazardous|no\s*hazard|all\s*clear|safe|continue", low):
        return "clear"
    return None


async def _handle_hazmat_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], text: str, selection: dict[str, Any]
) -> None:
    rate = _find_rate(state_data.get("rates", []), str(state_data.get("selected_rate_id")))
    if not rate:
        state_data["state"] = SHOWING_RATES
        save_state(ctx, sender, state_data)
        await send_text(ctx, sender, "Let's pick a shipping option again.")
        return

    signal = _hazmat_signal(text, selection)
    if signal == "stop":
        # Don't purchase. Point at the two carrier-specific hazmat guides and
        # note that common items often ship without special declaration, so the
        # user isn't left assuming everything is simply refused.
        state_data["state"] = DONE
        save_state(ctx, sender, state_data)
        await send_text(
            ctx,
            sender,
            "Understood - I won't buy this label. Hazardous or restricted items need the "
            "carrier's special-handling process, which this demo doesn't cover:\n\n"
            f"- USPS HAZMAT guide: {USPS_HAZMAT_GUIDE_URL}\n"
            f"- UPS Limited Quantity guide: {UPS_HAZMAT_GUIDE_URL}\n\n"
            "Note that many everyday items (for example nail polish or a phone with a "
            "small battery) can often ship without any special declaration - check the "
            "guides above. When you're ready, send any message to start a new package; "
            "your profile and payment stay in place.",
        )
        return
    if signal == "clear":
        await _maybe_offer_insurance(ctx, sender, state_data, rate)
        return

    await send_card(
        ctx,
        sender,
        "Tap a button above: 'Nothing hazardous, continue' or 'This needs special handling'.",
        hazmat_review_card(rate.provider),
    )


async def _maybe_offer_insurance(
    ctx: Context, sender: str, state_data: dict[str, Any], rate: RateOption
) -> None:
    """Insurance gate: skip entirely when the declared value is already covered
    for free by the chosen service, otherwise offer optional XCover insurance."""
    declared = float((state_data.get("package") or {}).get("declared_value_usd", 0) or 0)
    free_coverage = free_included_coverage_usd(rate.provider, rate.servicelevel_name)

    if declared <= free_coverage:
        if declared > 0:
            await send_text(
                ctx,
                sender,
                f"Your declared value of {_money(declared)} is already covered for free by "
                f"{_carrier_label(rate)} (up to {_money(free_coverage)}), so no extra "
                "insurance is needed.",
            )
        await _begin_purchase_approval(ctx, sender, state_data, rate)
        return

    if declared > MAX_INSURABLE_VALUE_USD:
        # XCover can't insure above this; proceed with just the free coverage
        # rather than dead-ending, and say so plainly.
        await send_text(
            ctx,
            sender,
            f"Heads up: declared values above {_money(MAX_INSURABLE_VALUE_USD)} can't be "
            f"insured through this demo, so only {_carrier_label(rate)}'s included "
            f"{_money(free_coverage)} applies.",
        )
        await _begin_purchase_approval(ctx, sender, state_data, rate)
        return

    premium = insurance_premium_usd(declared)
    state_data["state"] = AWAITING_INSURANCE_CHECK
    save_state(ctx, sender, state_data)
    narration = (
        f"{_carrier_label(rate)} includes {_money(free_coverage)} of coverage for free, but "
        f"you declared {_money(declared)}. I can insure the full value for about "
        f"{_money(premium)} more, or you can skip it."
    )
    await send_card(
        ctx,
        sender,
        narration,
        insurance_review_card(
            rate, free_coverage=free_coverage, declared_value=declared, premium=premium
        ),
    )


def _insurance_signal(text: str, selection: dict[str, Any]) -> str | None:
    action = selection.get("action")
    if action == "add_insurance":
        return "add"
    if action == "skip_insurance":
        return "skip"
    low = (text or "").lower()
    if re.search(r"add\s*insurance|insure|with\s*insurance|protect|yes", low):
        return "add"
    if re.search(r"skip|no\s*insurance|without\s*insurance|no\s*thanks", low):
        return "skip"
    return None


async def _handle_insurance_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], text: str, selection: dict[str, Any]
) -> None:
    rate = _find_rate(state_data.get("rates", []), str(state_data.get("selected_rate_id")))
    if not rate:
        state_data["state"] = SHOWING_RATES
        save_state(ctx, sender, state_data)
        await send_text(ctx, sender, "Let's pick a shipping option again.")
        return

    signal = _insurance_signal(text, selection)
    if signal == "skip":
        await _begin_purchase_approval(ctx, sender, state_data, rate)
        return
    if signal == "add":
        insured = await _requote_with_insurance(ctx, sender, state_data, rate)
        await _begin_purchase_approval(ctx, sender, state_data, insured)
        return

    declared = float((state_data.get("package") or {}).get("declared_value_usd", 0) or 0)
    free_coverage = free_included_coverage_usd(rate.provider, rate.servicelevel_name)
    await send_card(
        ctx,
        sender,
        "Tap a button above to add insurance or skip it.",
        insurance_review_card(
            rate,
            free_coverage=free_coverage,
            declared_value=declared,
            premium=insurance_premium_usd(declared),
        ),
    )


async def _requote_with_insurance(
    ctx: Context, sender: str, state_data: dict[str, Any], base_rate: RateOption
) -> RateOption:
    """Re-quote just the chosen service with ``extra.insurance`` set, and return
    a rate whose ``amount`` reflects the insured total.

    One extra Shippo call (not a full re-shop). If Shippo returns a real
    ``included_insurance_price`` we trust its total; in test mode it usually
    doesn't compute one, so we fall back to the documented 1.25% domestic
    premium on top of the base price. The result is stored back into the
    session's rate list so every downstream step (approval card, label payment,
    confirmation) sees the same insured price.
    """
    declared = float((state_data.get("package") or {}).get("declared_value_usd", 0) or 0)
    premium = insurance_premium_usd(declared)
    insured = base_rate.model_copy(
        update={
            "amount": round(base_rate.amount + premium, 2),
            "included_insurance_price": premium,
        }
    )

    pkg_dict = state_data.get("package") or {}
    try:
        pkg = PackageDetails(**pkg_dict)
        client = shippo_client()
        from_addr = sender_address_from_profile(state_data["sender_profile"])
        requoted = await asyncio.to_thread(
            client.rate_shop,
            from_addr,
            _to_address(pkg),
            _parcel(pkg),
            insurance_amount=declared,
        )
        match = next(
            (
                r
                for r in requoted
                if r.provider == base_rate.provider
                and r.servicelevel_token == base_rate.servicelevel_token
            ),
            None,
        )
        if match:
            if match.included_insurance_price > 0:
                # Shippo computed the premium; its amount already includes it.
                insured = match
            else:
                # Test mode didn't add it - keep the real (insured) rate_id but
                # reflect the documented premium in the amount we show/charge.
                insured = match.model_copy(
                    update={
                        "amount": round(base_rate.amount + premium, 2),
                        "included_insurance_price": premium,
                    }
                )
    except Exception as exc:  # noqa: BLE001 - fall back to the local estimate
        ctx.logger.warning(f"[insurance] re-quote failed, using local estimate: {exc}")

    # Persist the insured rate so all downstream lookups resolve to it.
    rates = [r for r in state_data.get("rates", []) if r.get("rate_id") != insured.rate_id]
    rates.append(insured.model_dump())
    state_data["rates"] = rates
    state_data["selected_rate_id"] = insured.rate_id
    save_state(ctx, sender, state_data)
    return insured


async def _begin_purchase_approval(
    ctx: Context, sender: str, state_data: dict[str, Any], rate: RateOption
) -> None:
    """Kick off the requires_approval purchase and send the review card.

    The first run of the Pydantic AI purchase agent defers on the gated
    ``purchase_label`` tool, returning a DeferredToolRequests we render as the
    review card. Approval later triggers the second Stripe charge, and only a
    successful charge resumes the tool (see :func:`_handle_approval_stage`).
    """
    deps = ShippingDeps(shippo=shippo_client(), selected_rate=rate)
    start = await start_purchase(deps, rate.rate_id)
    if not start.deferred:
        await send_text(
            ctx,
            sender,
            "I couldn't set up the purchase approval just now. Please try again.",
        )
        return
    state_data["selected_rate_id"] = rate.rate_id
    state_data["purchase_history_json"] = start.history_json
    state_data["purchase_tool_call_id"] = start.tool_call_id
    state_data["state"] = AWAITING_PURCHASE_APPROVAL
    save_state(ctx, sender, state_data)
    price = _money(rate.amount, rate.currency)
    lines = [
        "One last check before I buy the label:",
        f"- Carrier: {_carrier_label(rate)}",
    ]
    if rate.included_insurance_price > 0:
        lines.append(f"- Insurance: {_money(rate.included_insurance_price, rate.currency)}")
    lines.append(f"- Total: {price}")
    lines.append("")
    lines.append(f"Reply 'confirm' and I'll charge {price} for this label and buy it, or 'cancel'.")
    await send_card(ctx, sender, "\n".join(lines), purchase_review_card(rate))


async def _handle_approval_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], selection: dict[str, Any]
) -> None:
    action = selection.get("action")
    history_json = state_data.get("purchase_history_json") or ""
    tool_call_id = state_data.get("purchase_tool_call_id") or ""

    if action == "deny_purchase":
        deps = ShippingDeps(shippo=shippo_client())
        await resume_purchase(
            deps, history_json=history_json, tool_call_id=tool_call_id, approved=False
        )
        state_data["state"] = SHOWING_DETAIL
        save_state(ctx, sender, state_data)
        await send_text(
            ctx,
            sender,
            "Cancelled - no label was purchased and nothing was charged for shipping. "
            "You can pick a different option or confirm again.",
        )
        return

    rate = _find_rate(state_data.get("rates", []), str(state_data.get("selected_rate_id")))
    if action != "approve_purchase":
        if rate:
            await send_card(
                ctx, sender, "Please confirm or cancel the purchase:", purchase_review_card(rate)
            )
        return

    if not rate:
        await send_text(ctx, sender, "Something went wrong - let's pick a shipping option again.")
        state_data["state"] = SHOWING_RATES
        save_state(ctx, sender, state_data)
        return

    # Approving the review card above only records intent - it moves no money.
    # Charge a second, separate Stripe payment for the exact rate price before
    # the deferred tool is ever resumed with approval. A successful payment
    # resumes it with ``approved=True`` (handle_label_payment_success); a
    # failed/declined one resumes with ``approved=False`` and returns the user
    # to rate picking (handle_label_payment_failed).
    await payment.request_payment(
        ctx,
        sender,
        state_data,
        amount_cents=round(rate.amount * 100),
        description=f"{rate.provider} {rate.servicelevel_name} label - {rate.currency} {rate.amount:.2f}",
        purpose="label",
    )


async def _handle_label_payment_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], text: str
) -> None:
    """Awaiting the second (label-price) payment - manual 'paid' fallback or re-issue."""
    if text.lower() in _PAID_WORDS:
        if await payment.confirm_payment_via_text(ctx, sender):
            return
        await send_text(
            ctx,
            sender,
            "Stripe still shows this label payment as unpaid. Finish the checkout, then "
            "type 'paid' again.",
        )
        return

    rate = _find_rate(state_data.get("rates", []), str(state_data.get("selected_rate_id")))
    if not rate:
        state_data["state"] = SHOWING_RATES
        save_state(ctx, sender, state_data)
        await send_text(ctx, sender, "Something went wrong - let's pick a shipping option again.")
        return

    # Any other message while this second payment is outstanding -> re-send it.
    await payment.request_payment(
        ctx,
        sender,
        state_data,
        amount_cents=round(rate.amount * 100),
        description=f"{rate.provider} {rate.servicelevel_name} label - {rate.currency} {rate.amount:.2f}",
        purpose="label",
    )


async def handle_label_payment_success(
    ctx: Context, sender: str, state_data: dict[str, Any]
) -> None:
    """The second payment (the label's real price) succeeded - now actually buy it."""
    rate = _find_rate(state_data.get("rates", []), str(state_data.get("selected_rate_id")))
    deps = ShippingDeps(shippo=shippo_client(), selected_rate=rate)
    history_json = state_data.get("purchase_history_json") or ""
    tool_call_id = state_data.get("purchase_tool_call_id") or ""

    try:
        purchase = await resume_purchase(
            deps, history_json=history_json, tool_call_id=tool_call_id, approved=True
        )
    except Exception as exc:  # noqa: BLE001 - surface Shippo failures to the user
        if deps.purchase_result is not None:
            # The gated tool call itself succeeded - Shippo already issued the
            # label - and only the model's follow-up reply generation failed
            # afterward (e.g. a transient ASI:One hiccup). Use the real result
            # instead of telling the user their payment vanished.
            ctx.logger.warning(f"[purchase] label bought but final reply failed: {exc}")
            purchase = deps.purchase_result
        else:
            ctx.logger.error(f"[purchase] failed after payment: {exc}")
            state_data["state"] = SHOWING_DETAIL
            save_state(ctx, sender, state_data)
            await send_text(
                ctx,
                sender,
                f"Your payment went through, but the label purchase failed ({exc}). Please try "
                "again - you were not charged twice.",
            )
            return

    if purchase is None:
        state_data["state"] = SHOWING_DETAIL
        save_state(ctx, sender, state_data)
        await send_text(
            ctx, sender, "Something went wrong finalizing the purchase. Please try again."
        )
        return

    state_data["purchase"] = purchase.model_dump()
    save_state(ctx, sender, state_data)

    await _deliver_label(ctx, sender, purchase)
    await _offer_pickup_or_finish(ctx, sender, state_data, purchase, rate)


async def handle_label_payment_failed(
    ctx: Context, sender: str, state_data: dict[str, Any]
) -> None:
    """The second payment failed/was declined - cancel the tool, go back to rate picking."""
    deps = ShippingDeps(shippo=shippo_client())
    history_json = state_data.get("purchase_history_json") or ""
    tool_call_id = state_data.get("purchase_tool_call_id") or ""
    try:
        await resume_purchase(
            deps,
            history_json=history_json,
            tool_call_id=tool_call_id,
            approved=False,
            denial_message="The payment for this label failed, so the purchase was cancelled.",
        )
    except Exception as exc:  # noqa: BLE001 - this is best-effort cleanup
        ctx.logger.warning(f"[purchase] cancel-on-payment-failure had an issue: {exc}")

    state_data["state"] = SHOWING_RATES
    save_state(ctx, sender, state_data)
    rate_objs = [RateOption(**r) for r in state_data.get("rates", [])]
    tags = _tag_rates(rate_objs)
    curated = _curate_rates(rate_objs, tags)
    await send_card(
        ctx,
        sender,
        "That payment didn't go through, so the label wasn't purchased and you weren't "
        "charged. Pick an option to try again:\n\n"
        + rates_text_summary(curated, tags, total=len(rate_objs)),
        rates_carousel(curated, tags, total=len(rate_objs)),
    )


async def _offer_pickup_or_finish(
    ctx: Context,
    sender: str,
    state_data: dict[str, Any],
    purchase: PurchaseResult,
    rate: RateOption | None = None,
) -> None:
    rate = rate or _find_rate(state_data.get("rates", []), str(state_data.get("selected_rate_id")))
    provider = rate.provider if rate else purchase.provider
    zip_code = str((state_data.get("package") or {}).get("to_zip", ""))

    if rate and rate.supports_pickup():
        state_data["state"] = AWAITING_PICKUP
        save_state(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            f"{provider} supports scheduled pickups. Want me to arrange one?",
            pickup_form_card(provider),
        )
        return

    # Drop-off carriers: point to the carrier's own locator (ZIP appended).
    locator = rate.drop_off_url(zip_code) if rate else None
    state_data["state"] = DONE
    save_state(ctx, sender, state_data)
    if locator:
        await send_text(
            ctx,
            sender,
            f"{provider} doesn't support API pickups - drop your parcel at a nearby "
            f"location: {locator}",
        )
    await _send_confirmation(ctx, sender, purchase, rate)


async def _send_confirmation(
    ctx: Context, sender: str, purchase: PurchaseResult, rate: RateOption | None
) -> None:
    """The one place the TEST/SAMPLE disclaimer is said, clearly, exactly once."""
    carrier = _carrier_label(rate) if rate else purchase.provider
    narration = (
        f"You're all set - your {carrier or 'label'} is booked.\n\n"
        f"- Carrier: {carrier or 'n/a'}\n"
        f"- Tracking number: {purchase.tracking_number or 'n/a'}\n\n"
        "A quick note on test mode: this is a demo SAMPLE label. It's watermarked, can't be "
        "mailed, and its tracking number is simulated by Shippo, so it won't update on the "
        "carrier's website - that's expected here, not an error."
    )
    await send_card(ctx, sender, narration, confirmation_card(purchase, rate))


async def _handle_pickup_stage(
    ctx: Context, sender: str, state_data: dict[str, Any], selection: dict[str, Any]
) -> None:
    purchase = PurchaseResult(**state_data["purchase"])
    action = selection.get("action")
    rate = _find_rate(state_data.get("rates", []), str(state_data.get("selected_rate_id")))

    if action == "done" or (action and action not in {"schedule_pickup"}):
        state_data["state"] = DONE
        save_state(ctx, sender, state_data)
        await _send_confirmation(ctx, sender, purchase, rate)
        return

    client = shippo_client()
    try:
        pickup = await asyncio.to_thread(
            client.schedule_pickup,
            carrier_account=rate.carrier_account if rate else "",
            transaction_id=purchase.transaction_id,
            address=sender_address_from_profile(state_data["sender_profile"]),
            building_location_type=str(selection.get("building_location_type", "Front Door")),
            instructions=str(selection.get("instructions", "")),
        )
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning(f"[pickup] scheduling failed: {exc}")
        state_data["state"] = DONE
        save_state(ctx, sender, state_data)
        await send_text(
            ctx,
            sender,
            f"I couldn't schedule the pickup ({exc}). Your label is still valid - you can "
            "drop the parcel off instead.",
        )
        await _send_confirmation(ctx, sender, purchase, rate)
        return

    state_data["state"] = DONE
    save_state(ctx, sender, state_data)
    when = pickup.confirmed_start_time or "the requested window"
    await send_text(
        ctx,
        sender,
        f"Pickup {pickup.status.lower() or 'requested'} (confirmation "
        f"{pickup.confirmation_code or 'n/a'}), starting around {when}. No courier is "
        "actually dispatched for this demo.",
    )
    await _send_confirmation(ctx, sender, purchase, rate)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.debug(f"ACK from {sender} for {msg.acknowledged_msg_id}")

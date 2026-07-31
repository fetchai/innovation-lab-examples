"""Card-shape, curation, and wording tests for ``chat_proto.py``.

These lock in the concrete UX fixes from review:

* The carousel now matches the documented ASI:One schema (top-level
  ``title``/``subtitle``, a per-item ``id``, ``badges`` as ``{label, variant}``
  dicts) - the previous shape was missing all three, which is exactly why
  ASI:One silently fell back to a text wall instead of rendering a card.
* Rate shopping shows a short curated list (cheapest/fastest/recommended) by
  default instead of dumping every option, with a 'show all' escape hatch.
* The ship-from sender *name* is always the fixed demo placeholder, never
  read from env or (worse) the recipient's name.
* Empty 'Terms'/'Mode' rows are omitted instead of rendered as '-' placeholders.
* The final confirmation is the only place TEST/SAMPLE wording appears, and it
  sources the carrier from the rate the user actually picked (not the
  possibly-blank Shippo transaction field).
"""

from __future__ import annotations

import json

import pytest

# Skip cleanly (rather than erroring collection) if run outside the example venv.
pytest.importorskip("uagents")
pytest.importorskip("pydantic_ai")
pytest.importorskip("httpx")

import chat_proto
from shipping import FIXED_SENDER_NAME, PurchaseResult, RateOption


def _rate(rate_id: str, provider: str, amount: float, days: int = 3, terms: str = "") -> RateOption:
    return RateOption(
        rate_id=rate_id,
        provider=provider,
        servicelevel_name=f"{provider} Service",
        servicelevel_token=f"{provider.lower()}_svc",
        amount=amount,
        currency="USD",
        estimated_days=days,
        duration_terms=terms,
    )


RATES = [
    _rate("r_cheap", "USPS", 7.50, days=4),
    _rate("r_mid", "UPS", 14.00, days=3),
    _rate("r_fast", "FedEx", 40.00, days=1),
    _rate("r_pricey", "UPS", 90.00, days=1),
]


# sender profile (captured from the user, kept separate from the recipient)
_SENDER_PROFILE = {
    "from_name": "Jane Sender",
    "from_street1": "1 Market St.",
    "from_city": "San Francisco",
    "from_state": "CA",
    "from_zip": "94105",
    "from_country": "US",
    "from_phone": "",
    "from_email": "",
}


def test_sender_address_built_from_captured_profile_not_recipient() -> None:
    """The recipient's name must never leak into the sender address - the sender
    is built purely from the separately-captured profile dict."""
    addr = chat_proto.sender_address_from_profile(_SENDER_PROFILE)
    assert addr.name == "Jane Sender"
    assert addr.name != "Whatever The Recipient Typed"


def test_sender_profile_summary_mentions_the_captured_address() -> None:
    summary = chat_proto.sender_profile_summary(_SENDER_PROFILE)
    assert "Jane Sender" in summary
    assert "1 Market St." in summary


def test_sender_profile_form_card_has_no_default_env_dependency() -> None:
    """The form's placeholders are static hints (Shippo's canonical demo
    persona), not values pulled from any SHIP_FROM_* env var - there is no such
    env var anymore."""
    card = chat_proto.sender_profile_form_card()
    payload = json.loads(card["card_payload"])
    field_names = {f["name"] for f in payload["fields"]}
    assert field_names == {
        "from_name",
        "from_street1",
        "from_city",
        "from_state",
        "from_zip",
        "from_phone",
        "from_email",
    }
    name_field = next(f for f in payload["fields"] if f["name"] == "from_name")
    assert name_field["placeholder"] == FIXED_SENDER_NAME


def test_sender_from_selection_builds_a_sender_profile() -> None:
    profile = chat_proto._sender_from_selection(_SENDER_PROFILE)
    assert profile is not None
    assert profile.from_name == "Jane Sender"


# carousel schema
def test_carousel_matches_the_documented_asi_one_schema() -> None:
    tags = chat_proto._tag_rates(RATES)
    card = chat_proto.rates_carousel(RATES, tags)
    assert card["card_kind"] == "carousel"
    payload = json.loads(card["card_payload"])

    assert payload["title"]
    assert payload["subtitle"]
    assert len(payload["items"]) == len(RATES)
    for item, rate in zip(payload["items"], RATES):
        assert item["id"] == rate.rate_id
        assert item["title"]
        assert "primary_cta" in item
        assert item["primary_cta"]["selection"]["rate_id"] == rate.rate_id
        for badge in item.get("badges", []):
            assert set(badge) == {"label", "variant"}


def test_carousel_adds_a_tappable_see_all_tile_when_curated() -> None:
    """Seeing the full list must be a real tappable card element, not only a
    text hint - otherwise it's not discoverable without typing something."""
    tags = chat_proto._tag_rates(RATES)
    curated = chat_proto._curate_rates(RATES, tags)
    card = chat_proto.rates_carousel(curated, tags, total=len(RATES))
    payload = json.loads(card["card_payload"])

    assert len(payload["items"]) == len(curated) + 1
    tile = payload["items"][-1]
    assert tile["primary_cta"]["selection"]["action"] == "show_all_rates"
    assert str(len(RATES)) in tile["title"]


def test_carousel_has_no_see_all_tile_when_already_showing_everything() -> None:
    tags = chat_proto._tag_rates(RATES)
    card = chat_proto.rates_carousel(RATES, tags, total=len(RATES))
    payload = json.loads(card["card_payload"])
    assert len(payload["items"]) == len(RATES)


def test_curate_rates_picks_cheapest_fastest_recommended_deduped() -> None:
    tags = chat_proto._tag_rates(RATES)
    curated = chat_proto._curate_rates(RATES, tags)
    assert 1 <= len(curated) <= 3
    ids = {r.rate_id for r in curated}
    assert tags["cheapest"] in ids
    assert tags["fastest"] in ids
    assert tags["recommended"] in ids


def test_rates_text_summary_mentions_show_all_when_curated() -> None:
    tags = chat_proto._tag_rates(RATES)
    curated = chat_proto._curate_rates(RATES, tags)
    text = chat_proto.rates_text_summary(curated, tags, total=len(RATES))
    assert "show all" in text.lower()
    assert str(len(RATES)) in text


def test_show_all_rates_keyword_parses_to_action() -> None:
    selection = chat_proto.parse_selection("show all options please")
    assert selection.get("action") == "show_all_rates"


# Terms / dash-free rows
def test_rate_detail_card_omits_empty_terms_row() -> None:
    rate = _rate("r1", "USPS", 10.0, terms="")
    payload = json.loads(chat_proto.rate_detail_card(rate)["card_payload"])
    labels = [row["label"] for row in payload["summary_rows"]]
    assert "Terms" not in labels
    assert not any(row["value"] == "-" for row in payload["summary_rows"])


def test_rate_detail_card_includes_terms_when_present() -> None:
    rate = _rate("r1", "USPS", 10.0, terms="1-3 business days")
    payload = json.loads(chat_proto.rate_detail_card(rate)["card_payload"])
    rows = {row["label"]: row["value"] for row in payload["summary_rows"]}
    assert rows["Terms"] == "1-3 business days"


def test_purchase_review_card_has_no_mode_row() -> None:
    """TEST/SAMPLE wording belongs on the final confirmation only."""
    rate = _rate("r1", "USPS", 10.0)
    payload = json.loads(chat_proto.purchase_review_card(rate)["card_payload"])
    labels = [row["label"] for row in payload["summary_rows"]]
    assert "Mode" not in labels
    assert not any("TEST" in str(row["value"]) for row in payload["summary_rows"])


# final confirmation
def test_confirmation_card_sources_carrier_from_the_selected_rate() -> None:
    """Guards the blank-carrier bug: Shippo's transaction ``rate`` field comes
    back unexpanded as a bare id, so the confirmation must use the rate the
    user actually picked earlier in the conversation, not ``purchase.provider``."""
    purchase = PurchaseResult(
        transaction_id="txn_1",
        status="SUCCESS",
        test=True,
        label_url="https://deliver.goshippo.com/x.pdf",
        tracking_number="1Z999AA10123456784",
        provider="",  # simulates Shippo not expanding rate
    )
    rate = _rate("r1", "UPS", 14.0)
    payload = json.loads(chat_proto.confirmation_card(purchase, rate)["card_payload"])
    rows = {row["label"]: row["value"] for row in payload["summary_rows"]}
    assert rows["Carrier"] == "UPS UPS Service"
    assert rows["Tracking number"] == "1Z999AA10123456784"


def test_confirmation_card_mentions_test_sample_exactly_once() -> None:
    purchase = PurchaseResult(
        transaction_id="txn_1",
        status="SUCCESS",
        test=True,
        label_url="https://deliver.goshippo.com/x.pdf",
        tracking_number="1Z999AA10123456784",
    )
    rate = _rate("r1", "UPS", 14.0)
    payload = json.loads(chat_proto.confirmation_card(purchase, rate)["card_payload"])
    mentions = sum(
        1
        for row in payload["summary_rows"]
        if "TEST" in str(row["value"]) or "SAMPLE" in str(row["value"])
    )
    assert mentions == 1


def test_no_stray_resource_content_helpers_remain() -> None:
    """The broken duplicate-link artifact came from ExternalStorage/ResourceContent
    delivery; that code path was removed in favor of the direct label_url link."""
    assert not hasattr(chat_proto, "_download_bytes")


# natural-language rate text (no [], ~, (), or trademark glyphs)
def test_rate_text_and_carousel_are_free_of_technical_artifacts() -> None:
    rate = RateOption(
        rate_id="r_tm",
        provider="UPS",
        servicelevel_name="2nd Day Air\u00ae",
        servicelevel_token="ups_2nd_day",
        amount=64.92,
        currency="USD",
        estimated_days=2,
    )
    tags = chat_proto._tag_rates([rate])
    text = chat_proto.rates_text_summary([rate], tags, total=1)
    carousel = json.loads(chat_proto.rates_carousel([rate], tags)["card_payload"])
    title = carousel["items"][0]["title"]

    for artifact in ("[", "]", "~", "(", ")", "\u00ae", "USD ", "day(s)"):
        assert artifact not in text, f"found {artifact!r} in rate text"
        assert artifact not in title, f"found {artifact!r} in carousel title"
    assert "$64.92" in text  # money uses a $ sign, not 'USD 64.92'


# pre-flight sanity checks on the intake form
def _pkg_selection(**overrides: object) -> dict[str, object]:
    base = {
        "to_name": "Mrs Hippo",
        "to_street1": "965 Mission St",
        "to_city": "San Francisco",
        "to_state": "CA",
        "to_zip": "94105",
        "weight_lb": 2,
        "length_in": 5,
        "width_in": 5,
        "height_in": 5,
        "declared_value_usd": 100,
    }
    base.update(overrides)
    return base


def test_preflight_flags_nonpositive_dimensions() -> None:
    assert chat_proto._preflight_selection_error(_pkg_selection(weight_lb=0)) is not None
    assert chat_proto._preflight_selection_error(_pkg_selection(length_in=-1)) is not None


def test_preflight_flags_implausible_declared_value() -> None:
    assert (
        chat_proto._preflight_selection_error(_pkg_selection(declared_value_usd=50000)) is not None
    )
    assert chat_proto._preflight_selection_error(_pkg_selection(declared_value_usd=-5)) is not None


def test_preflight_passes_sane_package_and_ignores_prose() -> None:
    assert chat_proto._preflight_selection_error(_pkg_selection()) is None
    # A prose message (no numeric form fields) is not the form path -> no check.
    assert chat_proto._preflight_selection_error({"action": "select_rate"}) is None


# international fail-fast
def test_international_text_is_detected() -> None:
    assert chat_proto._looks_international_text("Send it to Toronto, Canada M5V 2T6") is True
    assert chat_proto._looks_international_text("965 Mission St, San Francisco, CA 94105") is False


def test_international_selection_is_detected_by_country_or_postal() -> None:
    assert chat_proto._looks_international_selection({"to_country": "CA"}) is True
    assert chat_proto._looks_international_selection({"to_zip": "M5V 2T6"}) is True
    assert (
        chat_proto._looks_international_selection({"to_zip": "94105", "to_country": "US"}) is False
    )

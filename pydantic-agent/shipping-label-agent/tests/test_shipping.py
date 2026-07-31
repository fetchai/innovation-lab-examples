"""Shippo test-mode client tests (no network — httpx.MockTransport).

Covers: the test-token guard, rate shopping (incl. the ``test:true`` assertion
and the zero-rates case), label purchase (incl. the ``test:true`` + ``SUCCESS``
assertions and a status that does not resolve to success), address validation
feedback, and pickup eligibility for carriers that don't support API pickups.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

# Skip cleanly (rather than erroring collection) if run outside the example venv.
pytest.importorskip("httpx")
pytest.importorskip("pydantic")

import httpx

from shipping import (
    Address,
    Parcel,
    PickupResult,
    RateOption,
    ShippoClient,
    ShippoError,
    address_diff,
    free_included_coverage_usd,
    insurance_premium_usd,
)

TEST_TOKEN = "shippo_test_dummy_token"

_TO = Address(
    name="Mrs Hippo", street1="965 Mission St", city="San Francisco", state="CA", zip="94105"
)
_FROM = Address(
    name="Mr Hippo", street1="215 Clayton St", city="San Francisco", state="CA", zip="94117"
)
_PARCEL = Parcel(length_in=5, width_in=5, height_in=5, weight_lb=2)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> ShippoClient:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="https://api.goshippo.com")
    return ShippoClient(TEST_TOKEN, client=http)


def _json(request: httpx.Request) -> dict[str, Any]:
    import json

    return json.loads(request.content or b"{}")


# token guard
def test_rejects_non_test_token() -> None:
    with pytest.raises(ShippoError):
        ShippoClient("live_token_should_never_run")


# rate shopping
def _shipment_response(rates: list[dict[str, Any]], *, test: bool = True) -> dict[str, Any]:
    return {"object_id": "ship_1", "status": "SUCCESS", "test": test, "rates": rates}


def _rate(object_id: str, provider: str, amount: str, days: int) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "provider": provider,
        "servicelevel": {"name": f"{provider} Ground", "token": f"{provider.lower()}_ground"},
        "amount": amount,
        "currency": "USD",
        "estimated_days": days,
        "carrier_account": "ca_1",
        "test": True,
    }


def test_rate_shop_returns_sorted_rates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/shipments/"
        rates = [_rate("r_expensive", "UPS", "24.30", 1), _rate("r_cheap", "USPS", "7.50", 3)]
        return httpx.Response(201, json=_shipment_response(rates))

    rates = _client(handler).rate_shop(_FROM, _TO, _PARCEL)
    assert [r.rate_id for r in rates] == ["r_cheap", "r_expensive"]  # cheapest first
    assert rates[0].amount == 7.50


def test_rate_shop_rejects_non_test_shipment() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201, json=_shipment_response([_rate("r", "USPS", "7.50", 3)], test=False)
        )

    with pytest.raises(ShippoError):
        _client(handler).rate_shop(_FROM, _TO, _PARCEL)


def test_rate_shop_zero_rates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=_shipment_response([]))

    assert _client(handler).rate_shop(_FROM, _TO, _PARCEL) == []


# insurance wire format (extra.insurance + included_insurance_price)
def test_rate_shop_sends_extra_insurance_and_parses_included_price() -> None:
    """The documented shipment-level ``extra.insurance`` flag must be sent as
    ``{amount, currency, content}`` and the returned ``included_insurance_price``
    parsed onto the rate. Source: docs.goshippo.com/docs/Shipments/ShippingInsurance
    """

    def handler(request: httpx.Request) -> httpx.Response:
        body = _json(request)
        assert body["extra"]["insurance"] == {
            "amount": "250.00",
            "currency": "USD",
            "content": "Merchandise",
        }
        rate = _rate("r_ins", "USPS", "9.55", 2)
        rate["included_insurance_price"] = "3.13"
        return httpx.Response(201, json=_shipment_response([rate]))

    rates = _client(handler).rate_shop(_FROM, _TO, _PARCEL, insurance_amount=250.0)
    assert rates[0].included_insurance_price == 3.13


def test_rate_shop_omits_extra_when_no_insurance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "extra" not in _json(request)
        return httpx.Response(201, json=_shipment_response([_rate("r", "USPS", "7.50", 3)]))

    rates = _client(handler).rate_shop(_FROM, _TO, _PARCEL)
    assert rates[0].included_insurance_price == 0.0


def test_free_coverage_defaults_to_100_with_ups_ground_saver_exception() -> None:
    assert free_included_coverage_usd("USPS", "Priority Mail") == 100.0
    assert free_included_coverage_usd("USPS", "Ground Advantage") == 100.0
    assert free_included_coverage_usd("UPS", "UPS Ground") == 100.0
    assert free_included_coverage_usd("UPS", "UPS Ground Saver") == 50.0


def test_insurance_premium_is_1_25_percent_domestic() -> None:
    assert insurance_premium_usd(400.0) == 5.0
    assert insurance_premium_usd(0.0) == 0.0


# purchase
def _transaction_response(*, status: str, test: bool) -> dict[str, Any]:
    return {
        "object_id": "txn_1",
        "status": status,
        "test": test,
        "label_url": "https://deliver.goshippo.com/txn_1.pdf",
        "tracking_number": "9271901755477000000000011",
        "tracking_url_provider": "https://tools.usps.com/go/TrackConfirmAction?tLabels=927",
        "rate": {
            "amount": "7.50",
            "currency": "USD",
            "provider": "USPS",
            "servicelevel_token": "usps_ground",
        },
        "messages": [],
    }


def test_purchase_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/transactions/"
        assert _json(request)["rate"] == "r_cheap"
        return httpx.Response(201, json=_transaction_response(status="SUCCESS", test=True))

    result = _client(handler).purchase("r_cheap")
    assert result.status == "SUCCESS"
    assert result.test is True
    assert result.label_url.endswith(".pdf")
    assert result.tracking_number


def test_purchase_requests_expand_rate() -> None:
    """Shippo's transaction ``rate`` is a plain object-id string by default -
    we must ask it to expand so provider/amount come back inline."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("expand") == "rate"
        return httpx.Response(201, json=_transaction_response(status="SUCCESS", test=True))

    result = _client(handler).purchase("r_cheap")
    assert result.provider == "USPS"


def test_purchase_backfills_provider_when_shippo_returns_unexpanded_rate() -> None:
    """If Shippo still returns ``rate`` as a bare string id (undocumented but
    possible in test mode), the caller's already-known selected rate fills in
    provider/service/amount so the confirmation never shows a blank carrier."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = _transaction_response(status="SUCCESS", test=True)
        body["rate"] = "819282d7ec8d4b1db3d03bbf8f0e1a7d"  # plain id, not expanded
        return httpx.Response(201, json=body)

    fallback = RateOption(
        rate_id="r_cheap",
        provider="USPS",
        servicelevel_name="Ground Advantage",
        servicelevel_token="usps_ground_advantage",
        amount=7.50,
        currency="USD",
    )
    result = _client(handler).purchase("r_cheap", fallback_rate=fallback)
    assert result.provider == "USPS"
    assert result.servicelevel_token == "usps_ground_advantage"
    assert result.amount == 7.50


def test_purchase_rejects_non_test_transaction() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=_transaction_response(status="SUCCESS", test=False))

    with pytest.raises(ShippoError):
        _client(handler).purchase("r_cheap")


def test_purchase_rejects_unsuccessful_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = _transaction_response(status="ERROR", test=True)
        body["messages"] = [{"text": "Invalid rate"}]
        return httpx.Response(201, json=body)

    with pytest.raises(ShippoError) as exc:
        _client(handler).purchase("r_cheap")
    assert "Invalid rate" in str(exc.value)


# address validation
def test_validate_address_flags_invalid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/addresses/"
        return httpx.Response(
            201,
            json={
                "is_complete": True,
                "validation_results": {
                    "is_valid": False,
                    "messages": [{"text": "The address as submitted could not be found."}],
                },
            },
        )

    validation = _client(handler).validate_address(_TO)
    assert validation.is_valid is False
    assert "could not be found" in validation.messages[0]


def test_validate_address_accepts_complete() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={"is_complete": True, "validation_results": {"is_valid": True, "messages": []}},
        )

    assert _client(handler).validate_address(_TO).is_valid is True


def test_validate_address_surfaces_corrected_city_when_valid() -> None:
    """Shippo can call an address "valid" (deliverable) while silently
    normalizing a city that doesn't match its own ZIP - e.g. "Irvine" for a
    ZIP whose USPS-preferred city is "Tustin". ``corrected`` must carry that
    normalized address so the caller can offer it as a suggestion instead of
    only trusting whatever the user typed."""
    mismatched = Address(
        name="Phu Quach", street1="30 Preston Pl", city="Irvine", state="CA", zip="92782"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={
                "is_complete": True,
                "validation_results": {"is_valid": True, "messages": []},
                "name": "Phu Quach",
                "street1": "30 Preston Pl",
                "city": "Tustin",
                "state": "CA",
                "zip": "92782",
                "country": "US",
            },
        )

    validation = _client(handler).validate_address(mismatched)
    assert validation.is_valid is True
    assert validation.corrected is not None
    assert validation.corrected.city == "Tustin"
    diff = address_diff(mismatched, validation.corrected)
    assert diff == {"city": ("Irvine", "Tustin")}


def test_validate_address_no_correction_when_it_matches() -> None:
    """No spurious "correction" when Shippo echoes back the same address
    (aside from case), so the confirm-address UX doesn't fire on every intake."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={
                "is_complete": True,
                "validation_results": {"is_valid": True, "messages": []},
                "name": _TO.name,
                "street1": _TO.street1,
                "city": _TO.city.upper(),
                "state": _TO.state,
                "zip": _TO.zip,
                "country": "US",
            },
        )

    validation = _client(handler).validate_address(_TO)
    assert validation.corrected is not None
    assert address_diff(_TO, validation.corrected) == {}


def test_validate_address_hints_a_correction_even_when_invalid() -> None:
    """Per Shippo's own docs example, an unmatched street can still come back
    with a corrected city/zip alongside the failure - useful as a hint even
    though the address must still be re-entered."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={
                "is_complete": False,
                "validation_results": {
                    "is_valid": False,
                    "messages": [{"text": "The address as submitted could not be found."}],
                },
                "name": "Shawn Ippotle",
                "street1": "215 HIPPO ST.",
                "city": "SAN FRANCISCO",
                "state": "CA",
                "zip": "94107",
                "country": "US",
            },
        )

    validation = _client(handler).validate_address(_FROM)
    assert validation.is_valid is False
    assert validation.corrected is not None
    assert validation.corrected.zip == "94107"


# carrier-agnostic behavior (USPS/UPS/FedEx/DHL Express)
def test_pickup_and_drop_off_cover_all_four_carriers() -> None:
    """The example is meant to work with any carrier account the user has
    connected in Shippo, not just USPS/UPS - FedEx and DHL Express must be
    handled identically to the two carriers used in most manual tests."""
    for provider, pickup_eligible in (
        ("USPS", True),
        ("DHL Express", True),
        ("UPS", False),
        ("FedEx", False),
    ):
        rate = RateOption(
            rate_id="r",
            provider=provider,
            servicelevel_name="Ground",
            servicelevel_token="x",
            amount=9.0,
            currency="USD",
        )
        assert rate.supports_pickup() is pickup_eligible
        # Every one of the four gets a real drop-off locator link regardless
        # of pickup eligibility (pickup-eligible carriers just don't need it).
        assert "94105" in (rate.drop_off_url("94105") or "")


# pickup eligibility
def test_pickup_eligibility_by_carrier() -> None:
    usps = RateOption(
        rate_id="r",
        provider="USPS",
        servicelevel_name="Priority",
        servicelevel_token="usps_priority",
        amount=9.0,
        currency="USD",
    )
    ups = RateOption(
        rate_id="r",
        provider="UPS",
        servicelevel_name="Ground",
        servicelevel_token="ups_ground",
        amount=9.0,
        currency="USD",
    )
    assert usps.supports_pickup() is True
    assert ups.supports_pickup() is False
    # A carrier without API pickup still gets a drop-off locator link.
    assert "94105" in (ups.drop_off_url("94105") or "")


def test_schedule_pickup_parses_confirmation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pickups/"
        body = _json(request)
        assert body["is_test"] is True
        assert body["transactions"] == ["txn_1"]
        return httpx.Response(
            201,
            json={
                "status": "CONFIRMED",
                "confirmation_code": "WTC310058750",
                "confirmed_start_time": "2020-05-09T12:00:00Z",
                "confirmed_end_time": "2020-05-09T23:59:59Z",
                "messages": None,
            },
        )

    result: PickupResult = _client(handler).schedule_pickup(
        carrier_account="ca_1", transaction_id="txn_1", address=_FROM
    )
    assert result.status == "CONFIRMED"
    assert result.confirmation_code == "WTC310058750"

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

import httpx
from pydantic import BaseModel, Field

SHIPPO_TEST_PREFIX = "shippo_test_"
DEFAULT_BASE_URL = "https://api.goshippo.com"
FIXED_SENDER_NAME = "Shawn Ippotle"
PICKUP_ELIGIBLE_PROVIDERS = {"USPS", "DHL Express"}

DROP_OFF_LOCATORS = {
    "USPS": "https://tools.usps.com/locations/?location={zip}",
    "DHL Express": "https://locator.dhl.com/?countryCode=US&postalCode={zip}",
    "UPS": "https://www.ups.com/dropoff?loc=en_US&postalCode={zip}",
    "FedEx": "https://www.fedex.com/en-us/dropoff-pickup-locations.html?searchtext={zip}",
}


USPS_PROHIBITED_URL = "https://pe.usps.com/text/pub52/welcome.htm"  # USPS Publication 52
UPS_PROHIBITED_URL = (
    "https://www.ups.com/us/en/support/shipping-support/"
    "shipping-special-care-regulated-items/prohibited-items"
)
USPS_HAZMAT_GUIDE_URL = (
    "https://support.goshippo.com/hc/en-us/articles/15969609312539-How-to-Ship-HAZMAT-with-USPS"
)
UPS_HAZMAT_GUIDE_URL = (
    "https://support.goshippo.com/hc/en-us/articles/38392469249563-How-to-Ship-HAZMAT-with-UPS"
)

DOMESTIC_INSURANCE_RATE = 0.0125
MAX_INSURABLE_VALUE_USD = 10_000.0
FREE_COVERAGE_DEFAULT_USD = 100.0


def free_included_coverage_usd(provider: str, servicelevel_name: str) -> float:
    """USD of coverage a carrier/service already includes at no extra cost."""
    p = (provider or "").strip().lower()
    s = (servicelevel_name or "").strip().lower()
    if p == "ups" and "ground saver" in s:
        return 50.0
    return FREE_COVERAGE_DEFAULT_USD


def insurance_premium_usd(declared_value_usd: float) -> float:
    """XCover premium (US domestic) to insure ``declared_value_usd``."""
    return round(max(declared_value_usd, 0.0) * DOMESTIC_INSURANCE_RATE, 2)


def is_domestic_country(country: str) -> bool:
    return (country or "US").strip().upper() in {"US", "USA", "UNITED STATES"}


class ShippoError(RuntimeError):
    """Raised when Shippo returns an error or a non-test / non-success response."""


class Address(BaseModel):
    """A postal address in the shape Shippo's address/shipment endpoints expect."""

    name: str
    street1: str
    city: str
    state: str
    zip: str
    country: str = "US"
    street2: str = ""
    phone: str = ""
    email: str = ""

    def to_shippo(self) -> dict[str, str]:
        return self.model_dump(exclude_defaults=False)


class Parcel(BaseModel):
    """Parcel dimensions/weight (imperial units, matching the intake card)."""

    length_in: float = Field(gt=0)
    width_in: float = Field(gt=0)
    height_in: float = Field(gt=0)
    weight_lb: float = Field(gt=0)

    def to_shippo(self) -> dict[str, str]:
        return {
            "length": str(self.length_in),
            "width": str(self.width_in),
            "height": str(self.height_in),
            "distance_unit": "in",
            "weight": str(self.weight_lb),
            "mass_unit": "lb",
        }


class AddressValidation(BaseModel):
    """Normalised result of Shippo's automatic US address validation.

    ``corrected`` is Shippo's own cleaned-up version of the address (e.g. a
    standardized city name for the ZIP) when it returned one - present on
    both valid *and* invalid results (see the docs' own example: an
    unmatched street still comes back with a corrected city/zip). It's
    ``None`` when Shippo didn't echo back any address fields at all.
    """

    is_valid: bool
    is_complete: bool
    messages: list[str] = Field(default_factory=list)
    corrected: Address | None = None


class RateOption(BaseModel):
    """One purchasable rate returned by the test-mode rate shop."""

    rate_id: str
    provider: str
    servicelevel_name: str
    servicelevel_token: str
    amount: float
    currency: str
    estimated_days: int | None = None
    duration_terms: str = ""
    carrier_account: str = ""
    test: bool = True
    # Insurance premium already folded into ``amount`` (>0 only on a rate that
    # was re-quoted with ``extra.insurance``). See ``ShippoClient.rate_shop``.
    included_insurance_price: float = 0.0

    def supports_pickup(self) -> bool:
        return self.provider in PICKUP_ELIGIBLE_PROVIDERS

    def drop_off_url(self, zip_code: str) -> str | None:
        template = DROP_OFF_LOCATORS.get(self.provider)
        if not template:
            return None
        return template.format(zip=quote_plus(zip_code))


class PurchaseResult(BaseModel):
    """Normalised result of buying a label via the test-mode transaction endpoint."""

    transaction_id: str
    status: str
    test: bool
    label_url: str
    tracking_number: str
    tracking_url_provider: str = ""
    amount: float | None = None
    currency: str = "USD"
    provider: str = ""
    servicelevel_token: str = ""


class PickupResult(BaseModel):
    """Normalised result of scheduling a carrier pickup in test mode."""

    status: str
    confirmation_code: str = ""
    confirmed_start_time: str = ""
    confirmed_end_time: str = ""
    messages: list[str] = Field(default_factory=list)


_DIFF_FIELDS = ("street1", "city", "state", "zip")


def address_diff(submitted: Address, corrected: Address) -> dict[str, tuple[str, str]]:
    """Field-level differences between what the user typed and what Shippo/USPS
    normalized it to (e.g. ``{"city": ("Irvine", "Tustin")}``).

    Comparison is case-insensitive and whitespace-trimmed so cosmetic
    normalization (Shippo often upper-cases city names) doesn't get flagged
    as a "correction" that isn't actually meaningful to the user.
    """
    diff: dict[str, tuple[str, str]] = {}
    for field in _DIFF_FIELDS:
        typed = str(getattr(submitted, field, "") or "").strip()
        found = str(getattr(corrected, field, "") or "").strip()
        if found and typed.casefold() != found.casefold():
            diff[field] = (typed, found)
    return diff


def _messages_to_strings(raw: Any) -> list[str]:
    """Shippo ``messages`` come back as strings or ``{"text": ...}`` dicts."""
    out: list[str] = []
    if isinstance(raw, list):
        for m in raw:
            if isinstance(m, dict):
                text = m.get("text") or m.get("source") or ""
                if text:
                    out.append(str(text))
            elif m:
                out.append(str(m))
    return out


class ShippoClient:
    """Minimal, test-mode-only wrapper over the Shippo REST API."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not token.startswith(SHIPPO_TEST_PREFIX):
            raise ShippoError(
                f"Refusing to run: SHIPPO_TOKEN must be a test token starting with "
                f"'{SHIPPO_TEST_PREFIX}'. This example never touches live Shippo."
            )
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(base_url=self._base_url, timeout=timeout)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"ShippoToken {self._token}",
            "Content-Type": "application/json",
        }

    def _post(
        self, path: str, payload: dict[str, Any], *, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        resp = self._client.post(path, json=payload, headers=self.headers, params=params)
        if resp.status_code >= 400:
            raise ShippoError(
                f"Shippo {path} returned HTTP {resp.status_code}: {self._error_detail(resp)}"
            )
        data: dict[str, Any] = resp.json()
        return data

    @staticmethod
    def _error_detail(resp: httpx.Response) -> str:
        """Shippo's real error reason, not a blind slice of the raw body.

        Error responses often echo the whole submitted object back before the
        actual explanation, e.g. a 400 from ``/pickups/`` echoes the full
        address/location first and puts ``messages`` after it. A fixed-length
        slice of ``resp.text`` can (and did) cut off before ever reaching it.
        Falls back to a short slice only if the body isn't the JSON shape
        Shippo documents.
        """
        try:
            body = resp.json()
        except ValueError:
            return resp.text[:400]
        if isinstance(body, dict):
            messages = _messages_to_strings(body.get("messages"))
            if messages:
                return "; ".join(messages)
            detail = body.get("detail")
            if detail:
                return str(detail)
        return resp.text[:400]

    def validate_address(self, address: Address) -> AddressValidation:
        """Create an address object; US addresses are validated automatically.

        Per Shippo's own docs, the response echoes back a (possibly
        corrected/standardized) address at the top level alongside
        ``validation_results`` - even for an address that fails validation.
        We surface that corrected address so the caller can offer it as a
        suggestion (e.g. a city that doesn't match its ZIP, like "Irvine"
        for a ZIP whose USPS-preferred city is "Tustin") instead of silently
        trusting whichever one - typed or corrected - happens to be right.
        """
        payload = {**address.to_shippo(), "validate": True}
        data = self._post("/addresses/", payload)
        results = data.get("validation_results") or {}
        messages = _messages_to_strings(results.get("messages"))
        # Shippo omits ``is_valid`` when it could not run validation at all; treat a
        # complete address with no error messages as acceptable so the example does
        # not dead-end on carriers/addresses Shippo cannot verify in test mode.
        is_complete = bool(data.get("is_complete", False))
        raw_valid = results.get("is_valid")
        is_valid = bool(raw_valid) if raw_valid is not None else (is_complete and not messages)

        corrected: Address | None = None
        if data.get("street1") or data.get("city") or data.get("zip"):
            try:
                corrected = Address(
                    name=str(data.get("name") or address.name),
                    street1=str(data.get("street1") or ""),
                    street2=str(data.get("street2") or ""),
                    city=str(data.get("city") or ""),
                    state=str(data.get("state") or ""),
                    zip=str(data.get("zip") or ""),
                    country=str(data.get("country") or address.country),
                    phone=str(data.get("phone") or ""),
                    email=str(data.get("email") or ""),
                )
            except (TypeError, ValueError):
                corrected = None

        return AddressValidation(
            is_valid=is_valid, is_complete=is_complete, messages=messages, corrected=corrected
        )

    def rate_shop(
        self,
        address_from: Address,
        address_to: Address,
        parcel: Parcel,
        *,
        insurance_amount: float | None = None,
        insurance_currency: str = "USD",
        insurance_content: str = "Merchandise",
    ) -> list[RateOption]:
        """Create a shipment and return its test-mode rates (cheapest first).

        When ``insurance_amount`` is given, Shippo's documented shipment-level
        ``extra.insurance`` flag is set (``{amount, currency, content}``), and
        each returned rate's ``included_insurance_price`` reflects the premium
        already folded into its ``amount``. Source:
        https://docs.goshippo.com/docs/Shipments/ShippingInsurance
        """
        payload: dict[str, Any] = {
            "address_from": address_from.to_shippo(),
            "address_to": address_to.to_shippo(),
            "parcels": [parcel.to_shippo()],
            "async": False,
        }
        if insurance_amount is not None and insurance_amount > 0:
            payload["extra"] = {
                "insurance": {
                    "amount": f"{insurance_amount:.2f}",
                    "currency": insurance_currency,
                    "content": insurance_content,
                }
            }
        data = self._post("/shipments/", payload)

        if data.get("test") is not True:
            raise ShippoError(
                "Expected a test-mode shipment (test=true) but Shippo returned "
                f"test={data.get('test')!r}. Aborting — this example is test-only."
            )

        rates: list[RateOption] = []
        for r in data.get("rates", []):
            try:
                rates.append(
                    RateOption(
                        rate_id=r["object_id"],
                        provider=r.get("provider", ""),
                        servicelevel_name=(r.get("servicelevel") or {}).get("name", "")
                        or r.get("servicelevel_name", ""),
                        servicelevel_token=(r.get("servicelevel") or {}).get("token", "")
                        or r.get("servicelevel_token", ""),
                        amount=float(r.get("amount", 0) or 0),
                        currency=r.get("currency", "USD"),
                        estimated_days=r.get("estimated_days"),
                        duration_terms=r.get("duration_terms", "") or "",
                        carrier_account=r.get("carrier_account", "") or "",
                        test=bool(r.get("test", True)),
                        included_insurance_price=float(r.get("included_insurance_price", 0) or 0),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        rates.sort(key=lambda o: o.amount)
        return rates

    def purchase(
        self,
        rate_id: str,
        *,
        label_file_type: str = "PDF",
        fallback_rate: RateOption | None = None,
    ) -> PurchaseResult:
        """Buy a label for ``rate_id``; asserts test=true and status=SUCCESS.

        Shippo's transaction response returns ``rate`` as a plain object-id
        *string* unless you ask it to expand
        (https://docs.goshippo.com/docs/API_Concepts/APIExpand) - so we
        request ``?expand=rate`` to get the provider/service/amount back
        inline. If Shippo still doesn't expand it (test mode has been known to
        skip this), ``fallback_rate`` - the same :class:`RateOption` the user
        picked during rate-shopping - fills in those fields instead, so the
        confirmation never shows a blank carrier.
        """
        payload = {"rate": rate_id, "label_file_type": label_file_type, "async": False}
        data = self._post("/transactions/", payload, params={"expand": "rate"})

        if data.get("test") is not True:
            raise ShippoError(
                "Transaction did not come back as test mode (test != true) — refusing "
                "to treat it as a valid SAMPLE label."
            )
        status = str(data.get("status", "")).upper()
        if status != "SUCCESS":
            messages = _messages_to_strings(data.get("messages")) or [
                f"status={status or 'UNKNOWN'}"
            ]
            raise ShippoError("Label purchase did not succeed: " + "; ".join(messages))

        rate = data.get("rate")
        amount: float | None = None
        currency = fallback_rate.currency if fallback_rate else "USD"
        provider = fallback_rate.provider if fallback_rate else ""
        servicelevel_token = fallback_rate.servicelevel_token if fallback_rate else ""
        if fallback_rate:
            amount = fallback_rate.amount
        if isinstance(rate, dict):
            amount = float(rate.get("amount", 0) or 0) or amount
            currency = rate.get("currency", currency)
            provider = rate.get("provider", provider) or provider
            servicelevel_token = rate.get("servicelevel_token", servicelevel_token) or (
                servicelevel_token
            )

        return PurchaseResult(
            transaction_id=str(data.get("object_id", "")),
            status=status,
            test=True,
            label_url=str(data.get("label_url", "")),
            tracking_number=str(data.get("tracking_number", "")),
            tracking_url_provider=str(data.get("tracking_url_provider", "") or ""),
            amount=amount,
            currency=currency,
            provider=provider,
            servicelevel_token=servicelevel_token,
        )

    def schedule_pickup(
        self,
        *,
        carrier_account: str,
        transaction_id: str,
        address: Address,
        start_hours_from_now: int = 2,
        window_hours: int = 4,
        building_location_type: str = "Front Door",
        instructions: str = "",
    ) -> PickupResult:
        """Schedule a USPS / DHL Express pickup for an already-purchased label."""
        now = datetime.now(UTC)
        start = now + timedelta(hours=start_hours_from_now)
        end = start + timedelta(hours=window_hours)
        location: dict[str, Any] = {
            "building_location_type": building_location_type,
            "address": address.to_shippo(),
        }
        if instructions:
            location["instructions"] = instructions
        payload = {
            "carrier_account": carrier_account,
            "location": location,
            "transactions": [transaction_id],
            "requested_start_time": start.isoformat().replace("+00:00", "Z"),
            "requested_end_time": end.isoformat().replace("+00:00", "Z"),
            "is_test": True,
        }
        data = self._post("/pickups/", payload)
        return PickupResult(
            status=str(data.get("status", "")),
            confirmation_code=str(data.get("confirmation_code", "") or ""),
            confirmed_start_time=str(data.get("confirmed_start_time", "") or ""),
            confirmed_end_time=str(data.get("confirmed_end_time", "") or ""),
            messages=_messages_to_strings(data.get("messages")),
        )

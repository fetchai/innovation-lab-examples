"""Pydantic AI logic tests, driven by FunctionModel/TestModel (no ASI:One call).

The centrepiece is the ``requires_approval=True`` gate on ``purchase_label``:

* ``start_purchase`` must *defer* - the label must NOT be bought yet.
* resuming with an approval buys the SAMPLE label and returns a PurchaseResult.
* resuming with a denial buys nothing.

Also verifies structured-output extraction (``extract_package``) runs offline.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

# Skip cleanly (rather than erroring collection) if run outside the example venv.
pytest.importorskip("pydantic_ai")
pytest.importorskip("httpx")

import httpx
from pydantic_ai import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from pydantic_agent import (
    PackageDetails,
    ShippingDeps,
    extract_package,
    resume_purchase,
    start_purchase,
)
from shipping import RateOption, ShippoClient

TEST_TOKEN = "shippo_test_dummy_token"
RATE_ID = "r_cheap"


def _fake_shippo(handler: Callable[[httpx.Request], httpx.Response]) -> ShippoClient:
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.goshippo.com")
    return ShippoClient(TEST_TOKEN, client=http)


def _successful_transaction_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        201,
        json={
            "object_id": "txn_1",
            "status": "SUCCESS",
            "test": True,
            "label_url": "https://deliver.goshippo.com/txn_1.pdf",
            "tracking_number": "9271901755477000000000011",
            "rate": {
                "amount": "7.50",
                "currency": "USD",
                "provider": "USPS",
                "servicelevel_token": "usps_ground",
            },
            "messages": [],
        },
    )


def _purchase_script(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Call the gated tool first; once it has returned, emit a final text reply."""
    for message in messages:
        for part in getattr(message, "parts", []):
            if part.__class__.__name__ == "ToolReturnPart":
                return ModelResponse(parts=[TextPart("Done — the test label was purchased.")])
    return ModelResponse(parts=[ToolCallPart("purchase_label", {"rate_id": RATE_ID})])


async def test_purchase_gate_defers_before_approval() -> None:
    """requires_approval must pause the purchase: no label bought on the first run."""
    deps = ShippingDeps(shippo=_fake_shippo(_successful_transaction_handler))
    model = FunctionModel(_purchase_script)

    start = await start_purchase(deps, RATE_ID, model=model)

    assert start.deferred is True
    assert start.tool_call_id  # a pending approval exists
    assert deps.purchase_result is None  # the label was NOT bought yet


async def test_purchase_completes_on_approval() -> None:
    deps = ShippingDeps(shippo=_fake_shippo(_successful_transaction_handler))
    model = FunctionModel(_purchase_script)

    start = await start_purchase(deps, RATE_ID, model=model)
    result = await resume_purchase(
        deps,
        history_json=start.history_json,
        tool_call_id=start.tool_call_id,
        approved=True,
        model=model,
    )

    assert result is not None
    assert result.status == "SUCCESS"
    assert result.test is True
    assert result.transaction_id == "txn_1"
    assert deps.purchase_result is result


async def test_purchase_cancelled_on_denial() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return _successful_transaction_handler(request)

    deps = ShippingDeps(shippo=_fake_shippo(handler))
    model = FunctionModel(_purchase_script)

    start = await start_purchase(deps, RATE_ID, model=model)
    result = await resume_purchase(
        deps,
        history_json=start.history_json,
        tool_call_id=start.tool_call_id,
        approved=False,
        model=model,
    )

    assert result is None
    assert deps.purchase_result is None
    assert calls == []  # the Shippo transaction endpoint was never hit


async def test_purchase_backfills_provider_from_selected_rate() -> None:
    """Real Shippo transaction responses return ``rate`` as a bare id string
    unless expanded; ``ShippingDeps.selected_rate`` is the fallback that keeps
    the final confirmation from showing a blank/unknown carrier."""

    def unexpanded_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={
                "object_id": "txn_2",
                "status": "SUCCESS",
                "test": True,
                "label_url": "https://deliver.goshippo.com/txn_2.pdf",
                "tracking_number": "9271901755477000000000022",
                "rate": "819282d7ec8d4b1db3d03bbf8f0e1a7d",  # plain id, not expanded
                "messages": [],
            },
        )

    selected_rate = RateOption(
        rate_id=RATE_ID,
        provider="UPS",
        servicelevel_name="Ground Saver",
        servicelevel_token="ups_ground_saver",
        amount=14.01,
        currency="USD",
    )
    deps = ShippingDeps(
        shippo=_fake_shippo(unexpanded_handler),
        selected_rate=selected_rate,
    )
    model = FunctionModel(_purchase_script)

    start = await start_purchase(deps, RATE_ID, model=model)
    result = await resume_purchase(
        deps,
        history_json=start.history_json,
        tool_call_id=start.tool_call_id,
        approved=True,
        model=model,
    )

    assert result is not None
    assert result.provider == "UPS"
    assert result.servicelevel_token == "ups_ground_saver"


async def test_structured_extraction_offline() -> None:
    pkg: PackageDetails = await extract_package(
        "Ship a 2 lb, 5x5x5 in box to Mrs Hippo, 965 Mission St, San Francisco, CA 94105.",
        model=TestModel(),
    )
    assert isinstance(pkg, PackageDetails)
    assert pkg.weight_lb > 0
    assert pkg.length_in > 0

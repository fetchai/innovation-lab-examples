from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import (
    Agent,
    DeferredToolRequests,
    DeferredToolResults,
    RunContext,
    ToolDenied,
)
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from shipping import PurchaseResult, RateOption, ShippoClient

ASI_ONE_BASE_URL = "https://api.asi1.ai/v1"
DEFAULT_ASI_MODEL = os.getenv("ASI_ONE_MODEL", "asi1-mini")


class PackageDetails(BaseModel):
    """Typed shipment intake - the structured-output target of ``extract_agent``."""

    to_name: str = Field(description="Recipient full name")
    to_street1: str = Field(description="Recipient street address, line 1")
    to_city: str = Field(description="Recipient city")
    to_state: str = Field(description="Recipient 2-letter state code")
    to_zip: str = Field(description="Recipient ZIP/postal code")
    to_country: str = Field(default="US", description="Recipient ISO-2 country code")
    weight_lb: float = Field(gt=0, description="Package weight in pounds")
    length_in: float = Field(gt=0, description="Package length in inches")
    width_in: float = Field(gt=0, description="Package width in inches")
    height_in: float = Field(gt=0, description="Package height in inches")
    declared_value_usd: float = Field(ge=0, default=0, description="Declared value in USD")


class SenderProfile(BaseModel):
    """The user's own ship-from address - captured once per session, right after
    payment, and kept separate from :class:`PackageDetails` (the recipient) so
    the sender can never accidentally end up being whatever the user typed as
    the recipient's name.
    """

    from_name: str = Field(description="Sender's full name")
    from_street1: str = Field(description="Sender's street address, line 1")
    from_city: str = Field(description="Sender's city")
    from_state: str = Field(description="Sender's 2-letter state code")
    from_zip: str = Field(description="Sender's ZIP/postal code")
    from_country: str = Field(default="US", description="Sender's ISO-2 country code")
    from_phone: str = Field(default="", description="Sender's phone number")
    from_email: str = Field(default="", description="Sender's email address")


@dataclass
class ShippingDeps:
    """Injected dependencies for the purchase agent (Pydantic AI DI)."""

    shippo: ShippoClient
    # The exact rate the user picked during rate-shopping. Shippo's real
    # transaction response only returns provider/service/amount inline when
    # expanded (see shipping.ShippoClient.purchase's docstring); this is the
    # fallback ``purchase_label`` uses so the confirmation never shows a
    # blank carrier.
    selected_rate: RateOption | None = None
    # Set by the ``purchase_label`` tool once a test label is bought, so the
    # caller can read the concrete result regardless of the model's final text.
    purchase_result: PurchaseResult | None = None


@dataclass
class PurchaseStart:
    """Outcome of the first (deferring) purchase run."""

    deferred: bool
    history_json: str
    tool_call_id: str = ""
    rate_id: str = ""


def build_asi1_model() -> OpenAIChatModel:
    """Build the ASI:One OpenAI-compatible chat model.

    A placeholder api_key keeps construction (and imports) working in tests,
    where a ``TestModel``/``FunctionModel`` is always passed to the run helpers
    and no real request is ever sent to ASI:One.
    """
    return OpenAIChatModel(
        DEFAULT_ASI_MODEL,
        provider=OpenAIProvider(
            base_url=ASI_ONE_BASE_URL,
            api_key=os.environ.get("ASI_ONE_API_KEY") or "not-used-in-tests",
        ),
    )


_DEFAULT_MODEL = build_asi1_model()

extract_agent: Agent[None, PackageDetails] = Agent(
    _DEFAULT_MODEL,
    output_type=PackageDetails,
    system_prompt=(
        "You extract US domestic shipping details from the user's message into the "
        "structured schema. Use 2-letter state codes and infer inches/pounds. If a "
        "value is missing, make a minimal reasonable assumption rather than inventing "
        "an address."
    ),
)


async def extract_package(text: str, *, model: Model | None = None) -> PackageDetails:
    """Extract typed :class:`PackageDetails` from free text (structured output)."""
    result = await extract_agent.run(text, model=model)
    return result.output


sender_extract_agent: Agent[None, SenderProfile] = Agent(
    _DEFAULT_MODEL,
    output_type=SenderProfile,
    system_prompt=(
        "You extract a US domestic ship-from (sender) profile from the user's message "
        "into the structured schema, including phone and email if the user gave them - "
        "USPS requires both to actually generate a label. Never invent a phone number or "
        "email address; leave the field blank if the user truly didn't provide one."
    ),
)


async def extract_sender_profile(text: str, *, model: Model | None = None) -> SenderProfile:
    """Extract typed :class:`SenderProfile` from free text (structured output)."""
    result = await sender_extract_agent.run(text, model=model)
    return result.output


purchase_agent: Agent[ShippingDeps, str | DeferredToolRequests] = Agent(
    _DEFAULT_MODEL,
    deps_type=ShippingDeps,
    output_type=[str, DeferredToolRequests],
    system_prompt=(
        "You buy a single shipping label by calling the purchase_label tool with the "
        "exact rate_id you are given. Never invent a rate_id. After the tool returns, "
        "reply with a one-line confirmation."
    ),
)


@purchase_agent.tool(requires_approval=True)
async def purchase_label(ctx: RunContext[ShippingDeps], rate_id: str) -> str:
    """Buy the shipping label for ``rate_id`` (TEST MODE only).

    Gated by ``requires_approval=True`` - Pydantic AI defers this call until the
    user approves it, so the body only runs after an explicit ``ToolApproved``.
    ``ShippoClient.purchase`` asserts ``test is True`` and ``status == 'SUCCESS'``.
    """
    result = await asyncio.to_thread(
        ctx.deps.shippo.purchase, rate_id, fallback_rate=ctx.deps.selected_rate
    )
    ctx.deps.purchase_result = result
    return (
        f"Purchased TEST label {result.transaction_id} "
        f"({result.provider} {result.servicelevel_token}), tracking {result.tracking_number}."
    )


def _dump_history(messages: list[ModelMessage]) -> str:
    return ModelMessagesTypeAdapter.dump_json(messages).decode("utf-8")


def _load_history(history_json: str) -> list[ModelMessage]:
    return list(ModelMessagesTypeAdapter.validate_json(history_json))


async def start_purchase(
    deps: ShippingDeps, rate_id: str, *, model: Model | None = None
) -> PurchaseStart:
    """First purchase run: the model calls the gated tool, which defers.

    Returns the serialized message history plus the pending tool-call id so the
    caller can resume with an approval or denial on the next chat turn.
    """
    result = await purchase_agent.run(
        f"Purchase the shipping label for rate_id={rate_id}.",
        deps=deps,
        model=model,
    )
    history_json = _dump_history(result.all_messages())
    output = result.output
    if isinstance(output, DeferredToolRequests) and output.approvals:
        pending = output.approvals[0]
        return PurchaseStart(
            deferred=True,
            history_json=history_json,
            tool_call_id=pending.tool_call_id,
            rate_id=rate_id,
        )
    # No approval was requested (e.g. the model declined to call the tool).
    return PurchaseStart(deferred=False, history_json=history_json, rate_id=rate_id)


async def resume_purchase(
    deps: ShippingDeps,
    *,
    history_json: str,
    tool_call_id: str,
    approved: bool,
    denial_message: str = "The user declined to purchase the label.",
    model: Model | None = None,
) -> PurchaseResult | None:
    """Resume the deferred purchase with an approve/deny decision.

    On approval the gated tool runs and buys the test label; the concrete
    :class:`PurchaseResult` is returned. On denial the tool never runs and
    ``None`` is returned.
    """
    results = DeferredToolResults()
    results.approvals[tool_call_id] = True if approved else ToolDenied(denial_message)
    await purchase_agent.run(
        message_history=_load_history(history_json),
        deferred_tool_results=results,
        deps=deps,
        model=model,
    )
    return deps.purchase_result

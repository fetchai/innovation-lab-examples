"""agent.py - uAgents bridge for Agentverse mailbox deployment.

Entry point for the Real Estate Search Agent. Handles:
- SearchRequest / FollowUpRequest messages
- Chat protocol (ASI:One compatible)
- Stripe payment gate (optional)
- Google Sheets delivery after payment confirmation
"""

import asyncio
import os
import time
import types
from dataclasses import dataclass, field

import aiohttp
from dotenv import load_dotenv
from pydantic import UUID4
from uagents import Agent, Context, Model, Protocol
from uagents.mailbox import StoredEnvelope
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
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

from sheets import (
    GoogleAuthRequiredError,
    create_listings_sheet,
    get_google_auth_message,
)
from stripe_payments import (
    STRIPE_AMOUNT_CENTS,
    create_checkout_session,
    is_configured as stripe_configured,
    verify_payment,
)
from workflow import WorkflowInput, run_search_only, run_workflow, resume_workflow

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# Message models
# ─────────────────────────────────────────────────────────────────────────────


class SearchRequest(Model):
    query: str
    user_id: str = ""


class FollowUpRequest(Model):
    query: str
    user_id: str = ""


class SearchResponse(Model):
    sheet_url: str = ""
    summary: str = ""
    num_results: int = 0
    session_id: str = ""
    error: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Pending-payment state
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _PendingPayment:
    user_id: str
    sender: str  # agent address to reply to after payment
    df: object  # pandas DataFrame with search results
    search: object  # SearchInput (location, listing_type, …)
    checkout_session_id: str
    is_chat: bool = False  # True when the request came via chat protocol
    created_at: float = field(default_factory=time.time)


_pending_payments: dict[str, _PendingPayment] = {}  # keyed by checkout_session_id
_pending_by_user: dict[str, str] = {}  # user_id → checkout_session_id

_PAYMENT_EXPIRY = 3600  # seconds — expire pending sessions after 1 hour


def _cleanup_expired() -> None:
    now = time.time()
    expired = [
        k for k, v in _pending_payments.items() if now - v.created_at > _PAYMENT_EXPIRY
    ]
    for k in expired:
        p = _pending_payments.pop(k, None)
        if p:
            _pending_by_user.pop(p.user_id, None)


def _store_pending(pending: _PendingPayment) -> None:
    _cleanup_expired()
    old_sid = _pending_by_user.pop(pending.user_id, None)
    if old_sid:
        _pending_payments.pop(old_sid, None)
    _pending_payments[pending.checkout_session_id] = pending
    _pending_by_user[pending.user_id] = pending.checkout_session_id


def _amount_str() -> str:
    """Format STRIPE_AMOUNT_CENTS as a dollar string, e.g. '1.99'."""
    return f"{STRIPE_AMOUNT_CENTS / 100:.2f}"


# ─────────────────────────────────────────────────────────────────────────────
# Agent setup
# ─────────────────────────────────────────────────────────────────────────────


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_agent() -> Agent:
    seed = _require_env("AGENT_SEED")
    name = os.getenv("AGENT_NAME", "real_estate_agent")
    network = os.getenv("AGENT_NETWORK", "testnet")
    use_mailbox = _bool_env("AGENT_MAILBOX", True)
    port = int(os.getenv("AGENT_PORT", "8000"))
    endpoint = os.getenv("AGENT_ENDPOINT", "").strip()

    kwargs = {
        "name": name,
        "seed": seed,
        "network": network,
        "port": port,
    }

    if endpoint:
        kwargs["endpoint"] = [endpoint]

    if use_mailbox:
        kwargs["mailbox"] = True

    return Agent(**kwargs)


agent = _build_agent()


def _patch_mailbox_bearer(api_key: str) -> None:
    """Replace attestation-based auth with Bearer token in the mailbox client.

    Agentverse v2 API requires 'Authorization: Bearer <api_key>' for mailbox
    polling, but uAgents 0.23.x still sends the old 'Agent <attestation>' header.
    This patch fixes the 401 auth error.
    """
    client = agent.mailbox_client
    if client is None:
        return

    async def _check_mailbox_loop(self):
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self._agentverse.agents_api}/{self._identity.address}/mailbox"
                    async with session.get(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                    ) as resp:
                        if resp.status == 200:
                            for item in await resp.json():
                                await self._handle_envelope(
                                    StoredEnvelope.model_validate(item)
                                )
                        elif resp.status == 404:
                            if not self._missing_mailbox_warning_logged:
                                self._logger.warning(
                                    "Agent mailbox not found: run scripts/register_mailbox.py"
                                )
                                self._missing_mailbox_warning_logged = True
                        else:
                            self._logger.error(
                                f"Failed to retrieve messages: {resp.status}:{await resp.text()}"
                            )
            except aiohttp.ClientConnectorError as ex:
                self._logger.warning(f"Failed to connect to mailbox server: {ex}")
            except Exception as ex:
                self._logger.exception(f"Got exception while checking mailbox: {ex}")
            await asyncio.sleep(self._poll_interval)

    async def _delete_envelope(self, uuid: UUID4):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self._agentverse.agents_api}/{self._identity.address}/mailbox/{uuid}"
                async with session.delete(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                ) as resp:
                    if resp.status >= 300:
                        self._logger.warning(
                            f"Failed to delete envelope: {await resp.text()}"
                        )
        except aiohttp.ClientConnectorError as ex:
            self._logger.warning(f"Failed to connect to mailbox server: {ex}")
        except Exception as ex:
            self._logger.exception(f"Got exception while deleting message: {ex}")

    client._check_mailbox_loop = types.MethodType(_check_mailbox_loop, client)
    client._delete_envelope = types.MethodType(_delete_envelope, client)


_agentverse_api_key = os.getenv("AGENTVERSE_API_KEY", "").strip()
if _agentverse_api_key:
    _patch_mailbox_bearer(_agentverse_api_key)


def _resolve_user_id(message_user_id: str, sender: str) -> str:
    value = (message_user_id or "").strip()
    return value if value else sender


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"Agent started: {agent.name}")
    ctx.logger.info(f"Address: {agent.address}")
    ctx.logger.info(f"Network: {os.getenv('AGENT_NETWORK', 'testnet')}")
    ctx.logger.info(
        f"Stripe payments: {'ENABLED ($' + _amount_str() + ')' if stripe_configured() else 'DISABLED (set STRIPE_SECRET_KEY to enable)'}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Payment protocol (seller role)
# ─────────────────────────────────────────────────────────────────────────────

_payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

_SHEET_OWNER_ID = os.getenv("GOOGLE_SHEET_USER_ID", "").strip()


async def _create_sheet_for_pending(pending: _PendingPayment) -> str:
    """Create the Google Sheet from a pending payment's data. Returns sheet_url."""
    sheet_user_id = _SHEET_OWNER_ID or pending.user_id
    return await asyncio.to_thread(
        create_listings_sheet,
        pending.df,
        pending.search.location,
        pending.search.listing_type,
        sheet_user_id,
    )


@_payment_proto.on_message(CommitPayment)
async def on_commit(ctx: Context, sender: str, msg: CommitPayment):
    """Handle payment confirmation from the user's wallet."""
    transaction_id = msg.transaction_id

    # Primary lookup: transaction_id is the checkout session ID (normal wallet flow)
    pending = _pending_payments.get(transaction_id)

    # Secondary lookup: transaction_id might be a PaymentIntent ID (pi_...).
    # Scan pending payments by the sender's agent address.
    if not pending and transaction_id.startswith("pi_"):
        pending = next(
            (p for p in _pending_payments.values() if p.sender == sender), None
        )
        if pending:
            ctx.logger.info(
                f"Resolved PI {transaction_id} → checkout session {pending.checkout_session_id}"
            )

    if not pending:
        ctx.logger.warning(
            f"CommitPayment for unknown/expired session: {transaction_id}"
        )
        await ctx.send(
            sender, RejectPayment(reason="Payment session not found or expired.")
        )
        return

    if msg.funds.payment_method != "stripe":
        await ctx.send(
            sender,
            RejectPayment(
                reason=f"Unsupported payment method: {msg.funds.payment_method}"
            ),
        )
        return

    ctx.logger.info(f"Verifying payment: {transaction_id}")
    try:
        paid = verify_payment(transaction_id)
    except Exception as exc:
        ctx.logger.exception("Stripe verification error")
        await ctx.send(
            sender, RejectPayment(reason=f"Payment verification failed: {exc}")
        )
        return

    if not paid:
        # Agentverse sends CommitPayment before Stripe finishes processing — retry a few times.
        for delay in (2, 4, 6):
            await asyncio.sleep(delay)
            try:
                paid = verify_payment(transaction_id)
            except Exception:
                break
            ctx.logger.info(f"Retry verify_payment={paid} (after {delay}s)")
            if paid:
                break

    if not paid:
        await ctx.send(
            sender,
            RejectPayment(
                reason="Payment not completed. Please finish the Stripe checkout first."
            ),
        )
        return

    ctx.logger.info("Payment verified — creating sheet...")
    try:
        sheet_url = await _create_sheet_for_pending(pending)
    except GoogleAuthRequiredError as exc:
        ctx.logger.error(f"Google auth required — {exc}")
        await ctx.send(
            sender, RejectPayment(reason=f"Google authorization required: {exc}")
        )
        return
    except Exception as exc:
        ctx.logger.exception("Sheet creation failed after payment")
        await ctx.send(sender, RejectPayment(reason=f"Sheet creation failed: {exc}"))
        return

    ctx.logger.info(f"Sheet created: {sheet_url}")

    _pending_payments.pop(pending.checkout_session_id, None)
    _pending_by_user.pop(pending.user_id, None)

    try:
        await ctx.send(
            sender, CompletePayment(transaction_id=pending.checkout_session_id)
        )
    except Exception as exc:
        ctx.logger.warning(f"CompletePayment send failed: {exc}")

    num_results = len(pending.df) if pending.df is not None else 0
    ctx.logger.info(f"Delivering sheet to {pending.sender} (is_chat={pending.is_chat})")
    try:
        if pending.is_chat:
            await ctx.send(
                pending.sender,
                ChatMessage(
                    content=[
                        TextContent(
                            text=(
                                f"Payment confirmed! Your Google Sheet is ready:\n{sheet_url}\n\n"
                                f"({num_results} listings in {pending.search.location})"
                            )
                        )
                    ]
                ),
            )
        else:
            await ctx.send(
                pending.sender,
                SearchResponse(
                    sheet_url=sheet_url,
                    summary=(
                        f"Payment confirmed! Found {num_results} listings in "
                        f"{pending.search.location}. Sheet: {sheet_url}"
                    ),
                    num_results=num_results,
                    session_id=pending.user_id,
                ),
            )
        ctx.logger.info(f"Sheet delivered to {pending.sender}: {sheet_url}")
    except Exception as exc:
        ctx.logger.error(f"Sheet delivery FAILED: {exc} — URL was: {sheet_url}")


@_payment_proto.on_message(RejectPayment)
async def on_reject(ctx: Context, sender: str, msg: RejectPayment):
    ctx.logger.info(f"Payment rejected by {sender}: {msg.reason}")


agent.include(_payment_proto, publish_manifest=True)


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper: run search → optionally request payment → return
# ─────────────────────────────────────────────────────────────────────────────


async def _search_and_request_payment(
    ctx: Context,
    sender: str,
    query: str,
    user_id: str,
    is_chat: bool,
) -> None:
    """
    Run search-only workflow, then:
      - If Stripe configured and listings found → create Stripe checkout, send
        RequestPayment. The sheet is created on CommitPayment.
      - If Stripe not configured → run full workflow (free mode) and reply directly.
      - If no listings found → reply directly with summary, no payment needed.
    """
    amount = _amount_str()

    if not stripe_configured():
        result = await run_workflow(WorkflowInput(user_request=query, user_id=user_id))
        if is_chat:
            reply = (
                f"{result.summary}\n\nResults sheet: {result.sheet_url}"
                if result.sheet_url
                else result.summary or "No results found."
            )
            await ctx.send(sender, ChatMessage(content=[TextContent(text=reply)]))
        else:
            error = ""
            if (
                not result.sheet_url
                and "Google authorization required" in result.summary
            ):
                error = result.summary
            await ctx.send(
                sender,
                SearchResponse(
                    sheet_url=result.sheet_url,
                    summary=result.summary,
                    num_results=result.num_results,
                    session_id=result.session_id or user_id,
                    error=error,
                ),
            )
        return

    result = await run_search_only(WorkflowInput(user_request=query, user_id=user_id))

    if result.num_results == 0 or result.pending_df is None:
        if is_chat:
            await ctx.send(
                sender,
                ChatMessage(
                    content=[TextContent(text=result.summary or "No listings found.")]
                ),
            )
        else:
            await ctx.send(
                sender,
                SearchResponse(
                    summary=result.summary,
                    num_results=0,
                    session_id=user_id,
                ),
            )
        return

    try:
        description = (
            f"{result.num_results} listings in {result.pending_search.location}"
        )
        chat_session_id = str(ctx.session) if hasattr(ctx, "session") else user_id
        checkout = create_checkout_session(user_id, chat_session_id, description)
    except Exception as exc:
        ctx.logger.exception("Stripe checkout creation failed")
        err_msg = f"Payment system unavailable: {exc}"
        if is_chat:
            await ctx.send(sender, ChatMessage(content=[TextContent(text=err_msg)]))
        else:
            await ctx.send(sender, SearchResponse(error=err_msg, session_id=user_id))
        return

    _store_pending(
        _PendingPayment(
            user_id=user_id,
            sender=sender,
            df=result.pending_df,
            search=result.pending_search,
            checkout_session_id=checkout["checkout_session_id"],
            is_chat=is_chat,
        )
    )

    await ctx.send(
        sender,
        RequestPayment(
            accepted_funds=[
                Funds(currency="USD", amount=amount, payment_method="stripe")
            ],
            recipient=str(ctx.agent.address),
            deadline_seconds=_PAYMENT_EXPIRY,
            reference=chat_session_id,
            description=(
                f"Pay ${amount} to receive your Google Sheet with "
                f"{result.num_results} real estate listings in {result.pending_search.location}."
            ),
            metadata={"stripe": checkout, "service": "real_estate_sheet"},
        ),
    )

    summary_text = (
        f"{result.summary}\n\n"
        f"To receive your Google Sheet, please complete the ${amount} payment "
        f"via Stripe checkout in your wallet."
    )
    if is_chat:
        await ctx.send(sender, ChatMessage(content=[TextContent(text=summary_text)]))
    else:
        await ctx.send(
            sender,
            SearchResponse(
                summary=summary_text,
                num_results=result.num_results,
                session_id=user_id,
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Chat protocol
# ─────────────────────────────────────────────────────────────────────────────

_chat_proto = Protocol(spec=chat_protocol_spec)


@_chat_proto.on_message(model=ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    """Handle messages from ASI:One and other chat-protocol clients."""
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))

    query = next(
        (item.text for item in msg.content if isinstance(item, TextContent)), ""
    ).strip()
    if not query:
        await ctx.send(
            sender,
            ChatMessage(
                content=[
                    TextContent(
                        text="Please send a search query, e.g. '3 bed house for sale in Austin TX under $400k'"
                    )
                ]
            ),
        )
        return

    try:
        await _search_and_request_payment(
            ctx, sender, query, user_id=sender, is_chat=True
        )
    except Exception as exc:
        ctx.logger.exception("Chat handler failed")
        await ctx.send(
            sender,
            ChatMessage(
                content=[TextContent(text=f"Sorry, something went wrong: {exc}")]
            ),
        )


@_chat_proto.on_message(model=ChatAcknowledgement)
async def handle_chat_ack(_ctx: Context, _sender: str, _msg: ChatAcknowledgement):
    pass  # acknowledgements from ASI:One — no action needed


agent.include(_chat_proto, publish_manifest=True)


# ─────────────────────────────────────────────────────────────────────────────
# SearchRequest / FollowUpRequest protocol
# ─────────────────────────────────────────────────────────────────────────────


@agent.on_message(model=SearchRequest)
async def handle_search(ctx: Context, sender: str, msg: SearchRequest):
    user_id = _resolve_user_id(msg.user_id, sender)
    ctx.logger.info(f"Search request from {sender} (user_id={user_id})")

    normalized_query = (msg.query or "").strip().lower()
    if normalized_query in {"/google-auth", "google auth", "connect google"}:
        instructions = get_google_auth_message(user_id)
        await ctx.send(
            sender,
            SearchResponse(
                summary=instructions,
                session_id=user_id,
                error=""
                if instructions.startswith("Google is already connected")
                else instructions,
            ),
        )
        return

    try:
        await _search_and_request_payment(
            ctx, sender, msg.query, user_id=user_id, is_chat=False
        )
    except Exception as exc:
        ctx.logger.exception("Search handler failed")
        await ctx.send(sender, SearchResponse(error=str(exc), session_id=user_id))


@agent.on_message(model=FollowUpRequest)
async def handle_followup(ctx: Context, sender: str, msg: FollowUpRequest):
    user_id = _resolve_user_id(msg.user_id, sender)
    ctx.logger.info(f"Follow-up request from {sender} (user_id={user_id})")

    if not stripe_configured():
        try:
            result = await resume_workflow(
                WorkflowInput(user_request=msg.query, user_id=user_id)
            )
            await ctx.send(
                sender,
                SearchResponse(
                    sheet_url=result.sheet_url,
                    summary=result.summary,
                    num_results=result.num_results,
                    session_id=result.session_id or user_id,
                ),
            )
        except Exception as exc:
            ctx.logger.exception("Follow-up handler failed")
            await ctx.send(sender, SearchResponse(error=str(exc), session_id=user_id))
        return

    try:
        await _search_and_request_payment(
            ctx, sender, msg.query, user_id=user_id, is_chat=False
        )
    except Exception as exc:
        ctx.logger.exception("Follow-up handler failed")
        await ctx.send(sender, SearchResponse(error=str(exc), session_id=user_id))


if __name__ == "__main__":
    agent.run()

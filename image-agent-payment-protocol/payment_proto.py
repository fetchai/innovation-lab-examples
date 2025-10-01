import os
from uuid import uuid4
from uagents import Context, Protocol

from protocol.payment import (
    Funds,
    RequestPayment,
    RejectPayment,
    CommitPayment,
    CancelPayment,
    CompletePayment,
    payment_protocol_spec,
)
# The equivalent import from uagents-core (kept here for reference only; DO NOT USE):
# from uagents_core.contrib.protocols.payment import (
#     Funds,
#     RequestPayment,
#     RejectPayment,
#     CommitPayment,
#     CancelPayment,
#     CompletePayment,
#     payment_protocol_spec,
# )

from skyfire import verify_and_charge, get_skyfire_service_id
from chat_proto import create_text_chat
from urllib.parse import quote


_agent_wallet = None


def set_agent_wallet(wallet):
    global _agent_wallet
    _agent_wallet = wallet


payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

USDC_FUNDS = Funds(currency="USDC", amount="0.001", payment_method="skyfire")


async def request_payment_from_user(ctx: Context, user_address: str):
    # Always advertise Skyfire USDC so the client shows the payment method
    accepted_funds = [USDC_FUNDS]
    skyfire_service_id = get_skyfire_service_id()

    metadata = {}
    if skyfire_service_id:
        metadata["skyfire_service_id"] = skyfire_service_id
    if _agent_wallet:
        metadata["provider_agent_wallet"] = str(_agent_wallet.address())

    payment_request = RequestPayment(
        accepted_funds=accepted_funds,
        recipient=ctx.agent.address,
        deadline_seconds=300,
        reference=str(uuid4()),
        description="ASI1 Image Gen: after payment, please send your image prompt (one image per payment)",
        metadata=metadata,
    )

    ctx.logger.info(f"Sending payment request to {user_address}: {payment_request}")
    await ctx.send(user_address, payment_request)


@payment_proto.on_message(CommitPayment)
async def handle_commit_payment(ctx: Context, sender: str, msg: CommitPayment):
    ctx.logger.info(f"Received payment commitment from {sender}: {msg}")

    payment_verified = False

    if msg.funds.payment_method == "skyfire" and msg.funds.currency == "USDC":
        try:
            payment_verified = await verify_and_charge(msg.transaction_id, "0.001", ctx.logger)
        except Exception as e:
            ctx.logger.error(f"Skyfire verify/charge error: {e}")
            payment_verified = False
    else:
        ctx.logger.error(f"Unsupported payment method: {msg.funds.payment_method}")
        payment_verified = False

    if payment_verified:
        ctx.logger.info(f"Payment verified successfully from {sender}")
        session_id = str(ctx.session)
        ctx.storage.set(f"{sender}:{session_id}:awaiting_prompt", True)
        ctx.storage.set(f"{sender}:{session_id}:verified_payment", True)
        await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
        await ctx.send(sender, create_text_chat("Please send your image prompt (one image will be generated)."))
    else:
        ctx.logger.error(f"Payment verification failed from {sender}")
        await ctx.send(sender, RejectPayment(reason="Payment verification failed"))


async def generate_image_after_payment(ctx: Context, user_address: str):
    from chat_proto import create_text_chat

    session_id = str(ctx.session)
    prompt = ctx.storage.get(f"prompt:{user_address}:{session_id}") or ctx.storage.get("current_prompt")
    if not prompt:
        ctx.logger.error("No prompt found in storage")
        await ctx.send(user_address, create_text_chat("Error: No prompt found"))
        return

    # Sanitize prompt for Pollinations (strip additional context/markup and limit length)
    def _sanitize_prompt(raw: str) -> str:
        p = raw
        try:
            # Drop bracketed markers and knowledge graph blocks if present
            if "[Additional Context]" in p:
                p = p.split("[Additional Context]")[0]
            if "<knowledge_graph>" in p:
                p = p.split("<knowledge_graph>")[0]
            # Remove any XML/HTML-like tags
            import re as _re
            p = _re.sub(r"<[^>]+>", " ", p)
            # Collapse whitespace and trim
            p = " ".join(p.split())
            # Limit to 200 chars to keep URL short/stable
            if len(p) > 200:
                p = p[:200]
        except Exception:
            p = raw.strip()
        return p or "an image"

    clean_prompt = _sanitize_prompt(prompt)
    ctx.logger.info(f"Generating image via Pollinations for prompt: {clean_prompt}")

    try:
        import requests as _r
        pollinations_url = f"https://image.pollinations.ai/prompt/{quote(clean_prompt)}?width=512&height=512"
        resp = _r.get(pollinations_url, timeout=90)
        ctype = resp.headers.get("Content-Type", "")
        if resp.status_code != 200 or not resp.content or not ctype.startswith("image/"):
            await ctx.send(user_address, create_text_chat("Image generation failed"))
            return

        image_bytes: bytes = resp.content
        mime_type: str = ctype or "image/png"

        # Upload to Agentverse External Storage and send as resource
        api_key = os.getenv("AGENTVERSE_API_KEY")
        base_url = os.getenv("AGENTVERSE_URL", "https://agentverse.ai")
        storage_url = f"{base_url}/v1/storage"

        if not api_key:
            await ctx.send(user_address, create_text_chat("Storage not configured. Please set AGENTVERSE_API_KEY to deliver the image."))
            return

        from uagents_core.storage import ExternalStorage
        from datetime import datetime, timezone
        from uuid import uuid4
        from uagents_core.contrib.protocols.chat import ResourceContent, Resource
        from uagents_core.contrib.protocols.chat import ChatMessage as AvChatMessage

        storage = ExternalStorage(api_token=api_key, storage_url=storage_url)
        asset_id = storage.create_asset(name=str(ctx.session), content=image_bytes, mime_type=mime_type)
        storage.set_permissions(asset_id=asset_id, agent_address=user_address)
        asset_uri = f"agent-storage://{storage.storage_url}/{asset_id}"

        await ctx.send(user_address, AvChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[
                ResourceContent(
                    type="resource",
                    resource_id=asset_id,
                    resource=Resource(uri=asset_uri, metadata={"mime_type": mime_type, "role": "generated-image"}),
                )
            ],
        ))
    except Exception as e:
        ctx.logger.error(f"Image generation error: {e}")
        await ctx.send(user_address, create_text_chat(f"Error generating image: {e}"))


@payment_proto.on_message(RejectPayment)
async def handle_reject_payment(ctx: Context, sender: str, msg: RejectPayment):
    """Seller-side handler required by AgentPaymentProtocol rules."""
    await ctx.send(
        sender,
        create_text_chat(
            "You rejected the payment. If you'd like to continue, reply and I'll send a new payment request."
        ),
    )


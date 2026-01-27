"""
Payment protocol for Gemini Imagen image generation agent.
"""

import base64
import os
import time
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)
from uagents_core.contrib.protocols.chat import (
    ChatMessage as AvChatMessage,
    Resource,
    ResourceContent,
    TextContent,
)

from shared import create_text_chat

_agent_wallet = None


def set_agent_wallet(wallet):
    global _agent_wallet
    _agent_wallet = wallet


payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

FET_FUNDS = Funds(currency="FET", amount="0.1", payment_method="fet_direct")
ACCEPTED_FUNDS = [FET_FUNDS]


def verify_fet_payment_to_agent(
    transaction_id: str,
    expected_amount_fet: str,
    sender_fet_address: str,
    recipient_agent_wallet,
    logger,
) -> bool:
    try:
        from cosmpy.aerial.client import LedgerClient, NetworkConfig

        testnet = os.getenv("FET_USE_TESTNET", "true").lower() == "true"
        network_config = (
            NetworkConfig.fetchai_stable_testnet()
            if testnet
            else NetworkConfig.fetchai_mainnet()
        )
        ledger = LedgerClient(network_config)
        expected_amount_micro = int(float(expected_amount_fet) * 10**18)
        logger.info(
            f"Verifying payment of {expected_amount_fet} FET from {sender_fet_address} "
            f"to {recipient_agent_wallet.address()}"
        )
        tx_response = ledger.query_tx(transaction_id)
        if not tx_response.is_successful():
            logger.error(f"Transaction {transaction_id} was not successful")
            return False
        recipient_found = False
        amount_found = False
        sender_found = False
        denom = "atestfet" if testnet else "afet"
        expected_recipient = str(recipient_agent_wallet.address())
        for event_type, event_attrs in tx_response.events.items():
            if event_type == "transfer":
                if event_attrs.get("recipient") == expected_recipient:
                    recipient_found = True
                    if event_attrs.get("sender") == sender_fet_address:
                        sender_found = True
                    amount_str = event_attrs.get("amount", "")
                    if amount_str and amount_str.endswith(denom):
                        try:
                            amount_value = int(amount_str.replace(denom, ""))
                            if amount_value >= expected_amount_micro:
                                amount_found = True
                        except Exception:
                            pass
        if recipient_found and amount_found and sender_found:
            logger.info(f"Payment verified: {transaction_id}")
            return True
        logger.error(
            f"Payment verification failed - recipient: {recipient_found}, "
            f"amount: {amount_found}, sender: {sender_found}"
        )
        return False
    except Exception as e:
        logger.error(f"FET payment verification failed: {e}")
        return False


async def request_payment_from_user(
    ctx: Context, user_address: str, description: str | None = None
):
    accepted_funds = [FET_FUNDS]
    metadata = {}
    fet_network = (
        "stable-testnet"
        if os.getenv("FET_USE_TESTNET", "true").lower() == "true"
        else "mainnet"
    )
    if _agent_wallet:
        metadata["provider_agent_wallet"] = str(_agent_wallet.address())
    metadata["fet_network"] = fet_network
    if description:
        metadata["content"] = description
    else:
        metadata["content"] = (
            "Please complete the payment to proceed. "
            "After payment, I will generate one image from your prompt."
        )
    payment_request = RequestPayment(
        accepted_funds=accepted_funds,
        recipient=str(_agent_wallet.address()) if _agent_wallet else "unknown",
        deadline_seconds=300,
        reference=str(uuid4()),
        description=description
        or "Gemini Imagen: after payment, I will generate one image from your prompt",
        metadata=metadata,
    )
    ctx.logger.info(f"Sending payment request to {user_address}")
    await ctx.send(user_address, payment_request)


def _allow_retry(ctx: Context, sender: str, session_id: str) -> bool:
    retry_key = f"{sender}:{session_id}:retry_count"
    try:
        current = int(ctx.storage.get(retry_key) or 0)
    except Exception:
        current = 0
    if current >= 1:
        return False
    ctx.storage.set(retry_key, current + 1)
    ctx.storage.set(f"{sender}:{session_id}:awaiting_prompt", True)
    ctx.storage.set(f"{sender}:{session_id}:verified_payment", True)
    return True


@payment_proto.on_message(CommitPayment)
async def handle_commit_payment(ctx: Context, sender: str, msg: CommitPayment):
    ctx.logger.info(f"Received payment commitment from {sender}")
    payment_verified = False
    if msg.funds.payment_method == "fet_direct" and msg.funds.currency == "FET":
        try:
            buyer_fet_wallet = None
            if isinstance(msg.metadata, dict):
                buyer_fet_wallet = msg.metadata.get("buyer_fet_wallet") or msg.metadata.get(
                    "buyer_fet_address"
                )
            if not buyer_fet_wallet:
                ctx.logger.error("Missing buyer_fet_wallet in CommitPayment.metadata")
            else:
                payment_verified = verify_fet_payment_to_agent(
                    transaction_id=msg.transaction_id,
                    expected_amount_fet=FET_FUNDS.amount,
                    sender_fet_address=buyer_fet_wallet,
                    recipient_agent_wallet=_agent_wallet,
                    logger=ctx.logger,
                )
        except Exception as e:
            ctx.logger.error(f"FET verify error: {e}")
    else:
        ctx.logger.error(f"Unsupported payment method: {msg.funds.payment_method}")
    if payment_verified:
        ctx.logger.info(f"Payment verified successfully from {sender}")
        await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
        await generate_image_after_payment(ctx, sender)
    else:
        ctx.logger.error(f"Payment verification failed from {sender}")
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=msg.transaction_id,
                reason="Payment verification failed",
            ),
        )


@payment_proto.on_message(RejectPayment)
async def handle_reject_payment(ctx: Context, sender: str, msg: RejectPayment):
    ctx.logger.info(f"Payment rejected by {sender}: {msg.reason}")
    await ctx.send(
        sender,
        create_text_chat(
            "Sorry, you denied the payment. Reply again and I'll send a new payment request."
        ),
    )


async def generate_image_after_payment(ctx: Context, user_address: str):
    from client import run_gemini_image_blocking

    session_id = str(ctx.session)
    prompt = ctx.storage.get(f"prompt:{user_address}:{session_id}") or ctx.storage.get(
        "current_prompt"
    )
    if not prompt:
        ctx.logger.error("No prompt found in storage")
        await ctx.send(user_address, create_text_chat("Error: No prompt found"))
        return
    ctx.logger.info(f"Generating image for verified payment: {prompt}")
    try:
        result = run_gemini_image_blocking(prompt=prompt)
        ctx.logger.info(
            f"Generation result: status={result.get('status')}, "
            f"has_image={bool(result.get('image_data'))}"
        )
        await process_image_result(ctx, user_address, result)
    except Exception as e:
        ctx.logger.error(f"Image generation error: {e}")
        await ctx.send(user_address, create_text_chat(f"Error generating image: {e}"))


async def process_image_result(ctx: Context, sender: str, result: dict):
    session_id = str(ctx.session)

    if result.get("status") == "failed" or "error" in result:
        err = result.get("error", "Unknown error")
        await ctx.send(sender, create_text_chat(f"Error: {err}"))
        if _allow_retry(ctx, sender, session_id):
            await ctx.send(
                sender,
                create_text_chat(
                    "Generation failed, but your payment is valid. "
                    "Send your image prompt again — you won't be charged again."
                ),
            )
        return

    image_bytes = result.get("image_data")
    content_type = result.get("content_type", "image/png")
    if not image_bytes:
        await ctx.send(sender, create_text_chat("Image generated but could not retrieve bytes"))
        if _allow_retry(ctx, sender, session_id):
            await ctx.send(
                sender,
                create_text_chat(
                    "Delivery failed, but your payment is valid. "
                    "Send your prompt again — no extra charge."
                ),
            )
        return

    from client import upload_image_to_tmpfiles

    image_url = await upload_image_to_tmpfiles(image_bytes, content_type)
    if not image_url:
        image_url = f"data:{content_type};base64,{base64.b64encode(image_bytes).decode()}"
    elif image_url.startswith("http://"):
        image_url = "https://" + image_url[7:]

    try:
        await ctx.send(
            sender,
            AvChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[
                    TextContent(type="text", text="Here is your generated image."),
                    ResourceContent(
                        type="resource",
                        resource_id=uuid4(),
                        resource=Resource(
                            uri=image_url,
                            metadata={
                                "mime_type": content_type,
                                "role": "image",
                            },
                        ),
                    ),
                ],
            ),
        )
        ctx.storage.remove(f"{sender}:{session_id}:retry_count")
        ctx.logger.info("Image sent successfully")
    except Exception as e:
        ctx.logger.error(f"Failed to send image: {e}")
        if _allow_retry(ctx, sender, session_id):
            await ctx.send(
                sender,
                create_text_chat(
                    "Could not send image, but your payment is valid. "
                    "Send your prompt again — no extra charge."
                ),
            )
        else:
            await ctx.send(
                sender,
                create_text_chat("Could not send image. Please try again or start a new session."),
            )

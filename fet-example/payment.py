"""
Payment protocol for ASI1 One LLM API agent.
"""

import os
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
    use_mainnet: bool = False,
) -> bool:
    """Verify FET payment transaction on Fetch.ai network."""
    try:
        from cosmpy.aerial.client import LedgerClient, NetworkConfig

        testnet = (
            os.getenv("FET_USE_TESTNET", "true").lower() == "true"
            if not use_mainnet
            else False
        )

        network_config = (
            NetworkConfig.fetchai_stable_testnet()
            if testnet
            else NetworkConfig.fetchai_mainnet()
        )
        ledger = LedgerClient(network_config)
        expected_amount_micro = int(float(expected_amount_fet) * 10**18)

        if not recipient_agent_wallet:
            logger.error("Recipient agent wallet is not set")
            return False

        expected_recipient = str(recipient_agent_wallet.address())

        logger.info(
            f"Verifying payment of {expected_amount_fet} FET from {sender_fet_address} "
            f"to {expected_recipient} on {'testnet' if testnet else 'mainnet'}"
        )

        tx_response = ledger.query_tx(transaction_id)
        if not tx_response.is_successful():
            logger.error(f"Transaction {transaction_id} was not successful")
            return False

        recipient_found = False
        amount_found = False
        sender_found = False
        denom = "atestfet" if testnet else "afet"

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
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


async def request_payment_from_user(
    ctx: Context, user_address: str, description: str | None = None
):
    session = str(ctx.session)

    # Build accepted funds list
    accepted_funds: list[Funds] = []

    # Add FET payment option
    fet_amount = os.getenv("FIXED_FET_AMOUNT", "0.1")
    accepted_funds.append(
        Funds(currency="FET", amount=str(fet_amount), payment_method="fet_direct")
    )

    if not accepted_funds:
        ctx.logger.warning(
            f"[payment] no accepted_funds; cannot send RequestPayment user={user_address} session={session}"
        )
        await ctx.send(
            user_address,
            AvChatMessage(
                content=[
                    TextContent(
                        type="text",
                        text="No payment methods are currently available. Please try again in a moment.",
                    )
                ]
            ),
        )
        return

    # Build metadata
    metadata: dict[str, str] = {
        "agent": "asi1-llm-agent",
        "service": "llm_processing",
    }

    use_testnet = os.getenv("FET_USE_TESTNET", "true").lower() == "true"
    fet_network = "stable-testnet" if use_testnet else "mainnet"
    metadata["fet_network"] = fet_network
    metadata["mainnet"] = "false" if use_testnet else "true"

    if _agent_wallet:
        metadata["provider_agent_wallet"] = str(_agent_wallet.address())

    if description:
        metadata["content"] = description
    else:
        metadata["content"] = (
            "Please complete the payment to proceed. "
            "After payment, I will process your request using ASI1 One LLM."
        )

    recipient_addr = (
        str(_agent_wallet.address()) if _agent_wallet else str(ctx.agent.address)
    )

    # Log payment request details
    funds_log = [
        {"method": f.payment_method, "currency": f.currency, "amount": f.amount}
        for f in accepted_funds
    ]
    ctx.logger.info(
        f"[payment] outbound RequestPayment user={user_address} session={session} "
        f"funds={funds_log} metadata={metadata} deadline_seconds=300"
    )

    payment_request = RequestPayment(
        accepted_funds=accepted_funds,
        recipient=recipient_addr,
        deadline_seconds=300,
        reference=session,
        description=description
        or "ASI1 One LLM: after payment, I will process your request",
        metadata=metadata,
    )

    # Send RequestPayment
    await ctx.send(user_address, payment_request)
    ctx.logger.info(
        f"[payment] RequestPayment sent to {user_address} with recipient {recipient_addr}"
    )


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
                buyer_fet_wallet = msg.metadata.get(
                    "buyer_fet_wallet"
                ) or msg.metadata.get("buyer_fet_address")
            if not buyer_fet_wallet:
                ctx.logger.error("Missing buyer_fet_wallet in CommitPayment.metadata")
            else:
                use_testnet = os.getenv("FET_USE_TESTNET", "true").lower() == "true"
                payment_verified = verify_fet_payment_to_agent(
                    transaction_id=msg.transaction_id,
                    expected_amount_fet=str(msg.funds.amount),
                    sender_fet_address=buyer_fet_wallet,
                    recipient_agent_wallet=_agent_wallet,
                    logger=ctx.logger,
                    use_mainnet=not use_testnet,
                )
        except Exception as e:
            ctx.logger.error(f"FET verify error: {e}")
    else:
        ctx.logger.error(f"Unsupported payment method: {msg.funds.payment_method}")
    if payment_verified:
        ctx.logger.info(f"Payment verified successfully from {sender}")
        await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
        await generate_response_after_payment(ctx, sender)
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


async def generate_response_after_payment(ctx: Context, user_address: str):
    from client import call_asi_one_api

    session_id = str(ctx.session)
    prompt = ctx.storage.get(f"prompt:{user_address}:{session_id}") or ctx.storage.get(
        f"current_prompt:{user_address}:{session_id}"
    )
    if not prompt:
        ctx.logger.error("No prompt found in storage")
        await ctx.send(user_address, create_text_chat("Error: No prompt found"))
        return
    ctx.logger.info(f"Processing request for verified payment: {prompt}")
    try:
        result = await call_asi_one_api(prompt=prompt)
        ctx.logger.info(
            f"API result: status={result.get('status')}, "
            f"has_image_url={bool(result.get('image_url'))}, "
            f"has_response_text={bool(result.get('response_text'))}"
        )
        await process_api_result(ctx, user_address, result)
    except Exception as e:
        ctx.logger.error(f"API call error: {e}")
        await ctx.send(user_address, create_text_chat(f"Error processing request: {e}"))


async def process_api_result(ctx: Context, sender: str, result: dict):
    session_id = str(ctx.session)

    if result.get("status") == "failed" or "error" in result:
        err = result.get("error", "Unknown error")
        await ctx.send(sender, create_text_chat(f"Error: {err}"))
        if _allow_retry(ctx, sender, session_id):
            await ctx.send(
                sender,
                create_text_chat(
                    "Request failed, but your payment is valid. "
                    "Send your request again — you won't be charged again."
                ),
            )
        return

    # Handle image URL response - send as markdown in chat (like the example)
    image_url = result.get("image_url")
    if image_url:
        try:
            # Send image as markdown in text content (matches ASI1 example)
            image_markdown = (
                f"Image generated successfully.\n\n![Generated image]({image_url})\n\n"
            )

            await ctx.send(
                sender,
                AvChatMessage(
                    timestamp=datetime.now(timezone.utc),
                    msg_id=uuid4(),
                    content=[
                        TextContent(type="text", text=image_markdown),
                    ],
                ),
            )
            ctx.storage.remove(f"{sender}:{session_id}:retry_count")
            ctx.logger.info(f"Image sent successfully as markdown: {image_url}")
        except Exception as e:
            ctx.logger.error(f"Failed to send image: {e}")
            if _allow_retry(ctx, sender, session_id):
                await ctx.send(
                    sender,
                    create_text_chat(
                        "Could not send image, but your payment is valid. "
                        "Send your request again — no extra charge."
                    ),
                )
            else:
                await ctx.send(
                    sender,
                    create_text_chat(
                        "Could not send image. Please try again or start a new session."
                    ),
                )
        return

    # Fallback: handle text response (for backward compatibility)
    response_text = result.get("response_text")
    if not response_text:
        await ctx.send(
            sender,
            create_text_chat("Response generated but could not retrieve image or text"),
        )
        if _allow_retry(ctx, sender, session_id):
            await ctx.send(
                sender,
                create_text_chat(
                    "Delivery failed, but your payment is valid. "
                    "Send your request again — no extra charge."
                ),
            )
        return

    try:
        await ctx.send(
            sender,
            AvChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[
                    TextContent(type="text", text=response_text),
                ],
            ),
        )
        ctx.storage.remove(f"{sender}:{session_id}:retry_count")
        ctx.logger.info("Response sent successfully")
    except Exception as e:
        ctx.logger.error(f"Failed to send response: {e}")
        if _allow_retry(ctx, sender, session_id):
            await ctx.send(
                sender,
                create_text_chat(
                    "Could not send response, but your payment is valid. "
                    "Send your request again — no extra charge."
                ),
            )
        else:
            await ctx.send(
                sender,
                create_text_chat(
                    "Could not send response. Please try again or start a new session."
                ),
            )

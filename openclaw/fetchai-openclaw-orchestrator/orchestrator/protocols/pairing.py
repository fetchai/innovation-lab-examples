"""
Device pairing protocol.

Handles pairing requests from local OpenClaw Connectors.
On success, stores the device record and the connector's agent address
so that task dispatches can be routed correctly.
"""

from __future__ import annotations

import logging

from uagents import Context, Protocol

from orchestrator.protocols.models import PairDeviceRequest, PairDeviceResponse

logger = logging.getLogger(__name__)

pairing_protocol = Protocol(name="device-pairing", version="0.1.0")


@pairing_protocol.on_message(PairDeviceRequest, replies={PairDeviceResponse})
async def handle_pairing(ctx: Context, sender: str, msg: PairDeviceRequest):
    """
    Register a device's public key and record the sender (connector)
    address for future task dispatch.
    """
    from orchestrator.agent import pairing_store

    ctx.logger.info(
        "Pairing request from user=%s device=%s sender=%s",
        msg.user_id,
        msg.device_id,
        sender,
    )

    # Basic validation
    if not msg.public_key_hex or len(msg.public_key_hex) != 64:
        await ctx.send(
            sender,
            PairDeviceResponse(
                user_id=msg.user_id,
                device_id=msg.device_id,
                status="rejected",
                message="Invalid public key (expected 64-char hex Ed25519 key).",
            ),
        )
        return

    # Store pairing record
    pairing_store.pair(
        user_id=msg.user_id,
        device_id=msg.device_id,
        public_key_hex=msg.public_key_hex,
        capabilities=msg.capabilities or ["weekly_report"],
    )

    # Remember the connector agent address for dispatching
    ctx.storage.set(f"connector:{msg.user_id}:{msg.device_id}", sender)

    await ctx.send(
        sender,
        PairDeviceResponse(
            user_id=msg.user_id,
            device_id=msg.device_id,
            status="paired",
            message="Device paired successfully.",
        ),
    )
    ctx.logger.info("Device %s paired for user %s", msg.device_id, msg.user_id)

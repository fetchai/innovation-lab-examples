from __future__ import annotations

import asyncio
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, Part, Role, DataPart
from a2a.utils import get_data_parts, new_agent_text_message

from uagents_adapter.a2a_outbound.ap2.artifacts import (
    CartContents,
    CartMandate,
    PaymentCurrencyAmount,
    PaymentDetailsInit,
    PaymentItem,
    PaymentMethodData,
    PaymentMandate,
    PaymentOptions,
    PaymentRequest,
    PaymentSuccess,
    compute_cart_hash,
)
from uagents_adapter.a2a_outbound.ap2.bridge_mapping import (
    CART_MANDATE_KEY,
    PAYMENT_MANDATE_KEY,
    PAYMENT_SUCCESS_KEY,
)
try:
    from .skyfire_payment import (
        is_skyfire_payment,
        detect_skyfire_token,
        process_skyfire_payment,
    )
except Exception:
    from skyfire_payment import (
        is_skyfire_payment,
        detect_skyfire_token,
        process_skyfire_payment,
    )


@dataclass
class CatalogItem:
    sku: str
    title: str
    price: float  # USDC


CATALOG: dict[str, CatalogItem] = {
    # Essentials (0.001 USDC)
    "shoe": CatalogItem(sku="shoe", title="Comfort Sneaker", price=0.0010),
    "book": CatalogItem(sku="book", title="Python Tips", price=0.0010),
    "pen": CatalogItem(sku="pen", title="Gel Pen", price=0.0010),
    # Standard electronics (0.001 USDC)
    "phone": CatalogItem(sku="phone", title="Phone", price=0.0010),
    "tablet": CatalogItem(sku="tablet", title="Tablet", price=0.0010),
    "watch": CatalogItem(sku="watch", title="Watch", price=0.0010),
    "headphones": CatalogItem(sku="headphones", title="Headphones", price=0.0010),
    "keyboard": CatalogItem(sku="keyboard", title="Keyboard", price=0.0010),
    "mouse": CatalogItem(sku="mouse", title="Mouse", price=0.0010),
    "speaker": CatalogItem(sku="speaker", title="Speaker", price=0.0010),
    "camera": CatalogItem(sku="camera", title="Camera", price=0.0010),
    "printer": CatalogItem(sku="printer", title="Printer", price=0.0010),
    "monitor": CatalogItem(sku="monitor", title="Monitor", price=0.0010),
    # Premium/infra (0.002 USDC)
    "laptop": CatalogItem(sku="laptop", title="Laptop", price=0.0020),
    "router": CatalogItem(sku="router", title="Router", price=0.0020),
    "switch": CatalogItem(sku="switch", title="Switch", price=0.0020),
    "firewall": CatalogItem(sku="firewall", title="Firewall", price=0.0020),
    "antivirus": CatalogItem(sku="antivirus", title="Antivirus", price=0.0020),
    "backup": CatalogItem(sku="backup", title="Backup", price=0.0020),
    "security": CatalogItem(sku="security", title="Security", price=0.0020),
    "networking": CatalogItem(sku="networking", title="Networking", price=0.0020),
    "storage": CatalogItem(sku="storage", title="Storage", price=0.0020),
    "cloud": CatalogItem(sku="cloud", title="Cloud", price=0.0020),
}


class StoreAgentExecutor(AgentExecutor):
    """A demo store that supports add/remove/list/cart/checkout; payment-first at checkout."""

    def __init__(self) -> None:
        # Single demo cart (process-wide) to ensure persistence across requests
        self._carts: Dict[str, Dict[str, int]] = {}

    def _get_cart(self, context_id: str) -> Dict[str, int]:
        # Use a global cart key so cart persists across requests/sessions in this demo
        return self._carts.setdefault("global", {})

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        msg = context.message
        data_parts: List[Dict[str, Any]] = get_data_parts(msg.parts) if msg else []

        # Handle PaymentMandate: confirm payment and deliver
        for data in data_parts:
            if PAYMENT_MANDATE_KEY in data:
                pm = PaymentMandate(**data[PAYMENT_MANDATE_KEY])
                pr = pm.payment_mandate_contents.payment_response
                tx_id = pr.request_id

                # Optional: Skyfire verification/charge if method_name == skyfire
                if is_skyfire_payment(pr):
                    token = detect_skyfire_token(pr)
                    if token:
                        total_item = pm.payment_mandate_contents.payment_details_total
                        expected_amount = str(total_item.amount.value)
                        sky = await process_skyfire_payment(token, expected_amount)
                        if not sky.get("success"):
                            await event_queue.enqueue_event(
                                new_agent_text_message(
                                    f"❌ Payment processing failed: {sky.get('error', 'unknown')}"
                                )
                            )
                            return
                        tx_id = sky.get("transaction_id", token)

                success = PaymentSuccess(transaction_id=tx_id)
                await event_queue.enqueue_event(
                    Message(
                        message_id=uuid.uuid4().hex,
                        role=Role.agent,
                        parts=[Part(root=DataPart(data={PAYMENT_SUCCESS_KEY: success.dict()}))],
                        context_id=context.context_id,
                        task_id=context.task_id,
                    )
                )
                # Clear cart and deliver
                cart = self._carts.pop("global", {})
                summary = ", ".join(f"{sku} x{qty}" for sku, qty in cart.items()) or "(empty)"
                await event_queue.enqueue_event(
                    new_agent_text_message(
                        f"🧾 Payment received (tx={tx_id}).\n📦 Your items: {summary}.\n✅ Delivered."
                    )
                )
                return

        # Otherwise parse user command
        user_text = (context.get_user_input() or "").strip()
        if not user_text:
            await event_queue.enqueue_event(new_agent_text_message(self._help_text()))
            return

        lowered = user_text.lower()
        if lowered in ("help", "?", "menu"):
            await event_queue.enqueue_event(new_agent_text_message(self._help_text()))
            return

        if lowered in ("list", "catalog"):
            await event_queue.enqueue_event(new_agent_text_message(self._catalog_text()))
            return

        if lowered.startswith("add "):
            await self._cmd_add(context, event_queue, lowered)
            return

        if lowered.startswith("remove "):
            await self._cmd_remove(context, event_queue, lowered)
            return

        if lowered in ("cart", "show cart"):
            await self._emit_cart_text(context, event_queue)
            return

        if lowered in ("checkout", "pay"):
            await self._emit_cart_mandate(context, event_queue)
            return

        if lowered in ("reset", "clear"):
            self._carts.pop("global", None)
            await event_queue.enqueue_event(new_agent_text_message("🧹 Cart cleared."))
            return

        # default: treat as add by sku=word
        if lowered in CATALOG:
            await self._cmd_add(context, event_queue, f"add {lowered} 1")
            return

        await event_queue.enqueue_event(
            new_agent_text_message(
                "I didn't recognize that. Type 'list' to see items or 'help' for commands."
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return

    async def _cmd_add(self, context: RequestContext, event_queue: EventQueue, lowered: str) -> None:
        # Supports: add <sku> [qty] [<sku> [qty]] ...
        body = lowered[len("add ") :].strip()
        if not body:
            await event_queue.enqueue_event(new_agent_text_message("Usage: add <sku> [qty] [<sku> [qty]] ..."))
            return

        tokens = body.split()
        i = 0
        added_pairs: list[tuple[str, int]] = []
        unknown: list[str] = []
        while i < len(tokens):
            sku = tokens[i]
            qty = 1
            # Next token as qty if it is an integer
            if i + 1 < len(tokens) and tokens[i + 1].isdigit():
                qty = int(tokens[i + 1])
                i += 2
            else:
                i += 1

            if sku not in CATALOG:
                unknown.append(sku)
                continue
            qty = max(1, qty)
            added_pairs.append((sku, qty))

        if not added_pairs and unknown:
            await event_queue.enqueue_event(
                new_agent_text_message("Unknown item(s). Type 'list' to see options.")
            )
            return

        if added_pairs:
            cart = self._get_cart(context.context_id)
            for sku, qty in added_pairs:
                cart[sku] = cart.get(sku, 0) + qty
            summary = ", ".join(f"{sku} x{qty}" for sku, qty in added_pairs)
            msg = f"➕ Added {summary}."
            if unknown:
                msg += f" (ignored: {', '.join(unknown)})"
            await event_queue.enqueue_event(new_agent_text_message(msg))
            await self._emit_cart_text(context, event_queue)
            return

    async def _cmd_remove(self, context: RequestContext, event_queue: EventQueue, lowered: str) -> None:
        # remove <sku>
        m = re.match(r"remove\s+(\w+)", lowered)
        if not m:
            await event_queue.enqueue_event(new_agent_text_message("Usage: remove <sku>"))
            return
        sku = m.group(1)
        cart = self._get_cart(context.context_id)
        if sku in cart:
            cart.pop(sku)
            await event_queue.enqueue_event(new_agent_text_message(f"➖ Removed {sku}."))
        else:
            await event_queue.enqueue_event(new_agent_text_message("Item not in cart."))
        await self._emit_cart_text(context, event_queue)

    async def _emit_cart_text(self, context: RequestContext, event_queue: EventQueue) -> None:
        cart = self._get_cart(context.context_id)
        if not cart:
            await event_queue.enqueue_event(new_agent_text_message("🧺 Cart is empty. Type 'list' to see items."))
            return
        lines: List[str] = ["🧺 Cart:"]
        total = 0.0
        for sku, qty in cart.items():
            item = CATALOG[sku]
            line_total = item.price * qty
            total += line_total
            lines.append(f"- {item.title} ({sku}) x{qty} = {line_total:.3f} USDC")
        lines.append(f"Total: {total:.3f} USDC\nType 'checkout' to pay.")
        await event_queue.enqueue_event(new_agent_text_message("\n".join(lines)))

    async def _emit_cart_mandate(self, context: RequestContext, event_queue: EventQueue) -> None:
        cart = self._get_cart(context.context_id)
        if not cart:
            await event_queue.enqueue_event(new_agent_text_message("🧺 Cart is empty. Add items before checkout."))
            return
        display_items: List[PaymentItem] = []
        total_value = 0.0
        for sku, qty in cart.items():
            ci = CATALOG[sku]
            line_total = ci.price * qty
            total_value += line_total
            display_items.append(
                PaymentItem(label=f"{ci.title} x{qty}", amount=PaymentCurrencyAmount(currency="USDC", value=line_total))
            )
        total_item = PaymentItem(label="Total", amount=PaymentCurrencyAmount(currency="USDC", value=total_value))
        cart_id = "cart-" + uuid.uuid4().hex[:10]
        pr = PaymentRequest(
            # Showcase Skyfire as the payment method so UI offers Skyfire pay
            method_data=[
                PaymentMethodData(
                    supported_methods="skyfire",
                    data={
                        "skyfire_service_id": os.getenv("SELLER_SERVICE_ID", ""),
                    },
                ),
            ],
            details=PaymentDetailsInit(id=cart_id, display_items=display_items, total=total_item),
            options=PaymentOptions(request_shipping=False),
        )
        contents = CartContents(
            id=cart_id,
            payment_request=pr,
            user_cart_confirmation_required=True,
            cart_expiry=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat() + "Z",
            merchant_name="Demo Store",
        )
        cart_mandate = CartMandate(
            contents=contents, merchant_authorization="demo_auth", cart_hash=compute_cart_hash(contents)
        )
        await event_queue.enqueue_event(
            Message(
                message_id=uuid.uuid4().hex,
                role=Role.agent,
                parts=[Part(root=DataPart(data={CART_MANDATE_KEY: cart_mandate.dict()}))],
                context_id=context.context_id,
                task_id=context.task_id,
            )
        )
        await asyncio.sleep(0.1)
        await event_queue.enqueue_event(new_agent_text_message("🧾 Please complete payment to confirm your order."))

    def _help_text(self) -> str:
        return (
            "Commands:\n"
            "- list | catalog\n"
            "- add <sku> [qty]\n"
            "- remove <sku>\n"
            "- cart | show cart\n"
            "- checkout | pay\n"
            "- reset\n\n"
            "SKUs: " + ", ".join(CATALOG.keys())
        )

    def _catalog_text(self) -> str:
        lines = ["🛍️ Catalog:"]
        for ci in CATALOG.values():
            lines.append(f"- {ci.title} ({ci.sku}) = {ci.price:.3f} USDC")
        lines.append("Type 'add <sku> [qty]' to add items.")
        return "\n".join(lines)



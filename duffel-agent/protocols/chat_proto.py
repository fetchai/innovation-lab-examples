# protocols/chat_proto.py
"""
Chat protocol adapter for the flights agent.

This module:
- Receives user chat messages.
- Loads / saves session state for the sender.
- Invokes the underlying agent/graph with user text + session state.
- Updates state with returned slots (origin, destination, date, passengers).
- Ensures user-friendly responses (no internal IDs shown).
- For now: focus only on greeting + collecting those search slots.
"""

from __future__ import annotations
import re
from typing import Dict, Any, Optional
from uuid import uuid4

from uagents import Protocol, Context
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)

# Protocol initialization
chat_proto = Protocol(spec=chat_protocol_spec)

def _get_session_key(sender: str, session_id: str) -> str:
    """Generate a unique storage key for sender + session."""
    return f"{sender}::{session_id}"

def _get_session_data(ctx: Context, sender: str, session_id: str) -> Dict[str, Any]:
    """Retrieve or initialize session data for this sender + session."""
    key = _get_session_key(sender, session_id)
    session_data = ctx.storage.get(key) or {}
    session_data.setdefault("state", {
        "origin": None,
        "destination": None,
        "date": None,
        "passengers": None,
        "greeted": False,
    })
    session_data.setdefault("history", [])
    return session_data

def _save_session_data(ctx: Context, sender: str, session_id: str, session_data: Dict[str, Any]) -> None:
    """Save session data for this sender + session."""
    key = _get_session_key(sender, session_id)
    ctx.storage.set(key, session_data)

def _extract_text(msg: ChatMessage) -> str:
    parts = []
    for item in msg.content or []:
        if isinstance(item, TextContent) and item.text:
            parts.append(item.text)
    return "\n".join(parts).strip()

async def _ack(ctx: Context, sender: str, msg: ChatMessage) -> None:
    try:
        await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
    except Exception:
        pass

@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await _ack(ctx, sender, msg)

    text = _extract_text(msg)
    if not text:
        # ignore empty
        return

    # Lazy import to break circular dependency
    from tools.openai_client import run_agent_turn

    # Get session-specific data
    session_id = str(ctx.session)
    session_data = _get_session_data(ctx, sender, session_id)
    
    state = session_data["state"]
    history = session_data["history"]

    # Invoke the agent/graph with current state
    result = run_agent_turn(
        user_text=text,
        session_state=state,
        history=history,
        session_id=f"{sender}::{session_id}"
        )

    # result expected to be {"content": <reply_text>, "state": <new_state_dict>, "history": <updated_history>}
    reply_text = result.get("content", "")
    new_state = result.get("state", {})
    updated_history = result.get("history", history)

    # Merge new_state into our stored state
    state.update(new_state)

    # Mark greeted if first interaction
    if not state.get("greeted"):
        state["greeted"] = True

    # Persist state and history for this session
    session_data["state"] = state
    session_data["history"] = updated_history
    _save_session_data(ctx, sender, session_id, session_data)

    # Check if list_orders was requested by the LLM
    if new_state.get("list_orders_requested"):
        # Retrieve order history from storage
        key_hist = f"booked_offers:{sender}"
        history_list = ctx.storage.get(key_hist) if ctx.storage.has(key_hist) else []
        if not isinstance(history_list, list):
            history_list = []
        
        # Format orders for display
        if not history_list:
            orders_text = "📋 You have no booked orders yet."
        else:
            lines = ["📋 Your Bookings:\n"]
            for i, item in enumerate(history_list[-10:], start=1):  # Show last 10 orders
                order_id = item.get("order_id", "—")
                booking_ref = item.get("booking_ref", "—")
                total = item.get("total", "—")
                timestamp = item.get("timestamp", "")
                method = item.get("method", "—")
                
                lines.append(f"{i}. Order: {order_id}")
                lines.append(f"   PNR: {booking_ref}")
                lines.append(f"   Total: {total}")
                lines.append(f"   Paid via: {method}")
                lines.append(f"   Date: {timestamp[:10] if timestamp else '—'}\n")
            
            lines.append("To cancel a booking, say \"cancel ord_xxxxx\"")
            orders_text = "\n".join(lines)
        
        # Send the orders list
        await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=orders_text)]))
        
        # Clear the flag
        state["list_orders_requested"] = False
        session_data["state"] = state
        _save_session_data(ctx, sender, session_id, session_data)
        return

    # Check if payment was requested by the LLM
    if new_state.get("payment_requested"):
        # Store passenger and offer data for payment protocol to use
        try:
            # Extract passenger data from conversation history
            passenger_data = {}
            for msg in updated_history:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    # Try to extract passenger details from user messages
                    import re
                    # Title
                    title_match = re.search(r'\b(mr|ms|mrs|miss|dr|mx)\.?\s', content, re.I)
                    if title_match:
                        passenger_data["title"] = title_match.group(1).lower()
                    # Names
                    name_match = re.search(r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b', content)
                    if name_match:
                        passenger_data["given_name"] = name_match.group(1)
                        passenger_data["family_name"] = name_match.group(2)
                    # DOB
                    dob_match = re.search(r'\b(19|20)\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b', content)
                    if dob_match:
                        passenger_data["born_on"] = dob_match.group(0)
                    # Gender
                    gender_match = re.search(r'\b(male|female|m|f|x)\b', content, re.I)
                    if gender_match:
                        g = gender_match.group(1).upper()[0]
                        passenger_data["gender"] = g if g in ['M', 'F', 'X'] else 'M'
                    # Email
                    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
                    if email_match:
                        passenger_data["email"] = email_match.group(0)
                    # Phone (must start with + and have 10+ digits, or be clearly a phone number)
                    # Avoid matching dates like 1997-01-31
                    phone_match = re.search(r'\+\d{10,}|\+\d[\d\s-]{9,}', content)
                    if phone_match:
                        phone_raw = phone_match.group(0).replace(' ', '').replace('-', '')
                        # Only store if it doesn't look like a date (not in format like 19970131)
                        if not (len(phone_raw) == 8 and phone_raw.startswith(('19', '20'))):
                            passenger_data["phone_number"] = phone_raw
            
            # Store passenger and offer data using the same keys as payment_proto expects
            if passenger_data:
                ctx.storage.set(f"passenger_1:{sender}:{session_id}", passenger_data)
                ctx.logger.info(f"Stored passenger data for payment: {passenger_data}")
            
            # Store selected offer ID if available (check both new_state and merged state)
            offer_id = new_state.get("selected_offer_id") or state.get("selected_offer_id")
            if offer_id:
                ctx.storage.set(f"selected_offer_id:{sender}:{session_id}", offer_id)
                ctx.logger.info(f"Stored offer ID: {offer_id}")
            else:
                ctx.logger.warning(f"No offer_id found in state when requesting payment!")
            
            # Store offer_passengers (passenger IDs from the offer)
            offer_passengers = new_state.get("offer_passengers") or state.get("offer_passengers")
            if offer_passengers:
                ctx.storage.set(f"offer_passengers:{sender}:{session_id}", offer_passengers)
                ctx.logger.info(f"Stored {len(offer_passengers)} offer passenger IDs")
        except Exception as e:
            ctx.logger.error(f"Failed to store passenger/offer data: {e}")
        
        # Import payment protocol function
        try:
            from protocols.payment_proto import request_payment_from_user
            description = new_state.get("payment_description", "Flight booking — pay to proceed")
            await request_payment_from_user(ctx, sender, description=description)
            # Clear the flag
            state["payment_requested"] = False
        except Exception as e:
            ctx.logger.error(f"Failed to send payment request: {e}")
    
    # Check if cancellation was confirmed and send email
    if new_state.get("cancellation_confirmed"):
        try:
            from protocols.payment_proto import _send_cancellation_email
            
            order_id = new_state.get("cancelled_order_id")
            refund_amount = new_state.get("cancelled_refund_amount")
            refund_currency = new_state.get("cancelled_refund_currency")
            
            # Get passenger email and booking ref from storage
            email_to = None
            pax_name = None
            booking_ref = None
            
            # Try to get passenger info from session storage
            passenger_key = f"passenger_1:{sender}:{session_id}"
            if ctx.storage.has(passenger_key):
                pax = ctx.storage.get(passenger_key)
                if isinstance(pax, dict):
                    email_to = pax.get("email")
                    pax_name = f"{pax.get('given_name', '')} {pax.get('family_name', '')}".strip()
            
            # Try to get booking ref from order history
            history_key = f"booked_offers:{sender}"
            if ctx.storage.has(history_key):
                history = ctx.storage.get(history_key)
                if isinstance(history, list):
                    for item in history:
                        if isinstance(item, dict) and item.get("order_id") == order_id:
                            booking_ref = item.get("booking_ref")
                            if not email_to:
                                # Try to get email from history if not in passenger storage
                                pass
                            break
            
            # Send cancellation email
            if email_to and order_id:
                refund_text = None
                if refund_amount and refund_currency:
                    refund_text = f"{refund_amount} {refund_currency}"
                
                _send_cancellation_email(
                    to_email=email_to,
                    passenger_name=pax_name or "Traveler",
                    order_id=order_id,
                    booking_ref=booking_ref,
                    refund_amount=refund_text
                )
                ctx.logger.info(f"Sent cancellation email to {email_to} for order {order_id}")
            
            # Clear the flag
            state["cancellation_confirmed"] = False
        except Exception as e:
            ctx.logger.error(f"Failed to send cancellation email: {e}")

    # Send reply (skip if empty - e.g., after payment request)
    if reply_text and reply_text.strip():
        await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=reply_text)]))

@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    # optional logging
    ctx.logger.info(f"Ack received from {sender} for {msg.acknowledged_msg_id}")
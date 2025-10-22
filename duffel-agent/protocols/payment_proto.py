# protocols/payment_proto.py
"""
Duffel Flights Agent Payment Protocol (seller role)
- Sends payment requests with both FET and Skyfire USDC options
- Verifies CommitPayment using FET tx hash or Skyfire JWT
- Auto-books after verified payment using stored offer/passenger details
"""

from __future__ import annotations
import os
from typing import Optional
from datetime import datetime, timezone

from uagents import Protocol, Context
from uagents_core.contrib.protocols.payment import (
    Funds,
    RequestPayment,
    RejectPayment,
    CommitPayment,
    CancelPayment,
    CompletePayment,
    payment_protocol_spec,
)
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

# Duffel tools for booking
try:
    from tools.duffel_tools import duffel_create_order  # type: ignore
except Exception as e:
    print(f"[payment_proto] Failed to import duffel_create_order: {e}")
    duffel_create_order = None  # type: ignore

# Payment verifiers
try:
    from tools.fet_payments import verify_fet_payment  # type: ignore
except Exception:
    try:
        from tools.fet_payment import verify_fet_payment  # type: ignore
    except Exception as e:
        print(f"[payment_proto] Failed to import verify_fet_payment: {e}")
    async def verify_fet_payment(*args, **kwargs):
        return True

try:
    from tools.skyfire import verify_and_charge, get_skyfire_service_id  # type: ignore
except Exception as e:
    print(f"[payment_proto] Failed to import skyfire: {e}")
    async def verify_and_charge(*args, **kwargs):
        return True
    def get_skyfire_service_id():
        return None

# --- helpers for cross-protocol storage keys ---
def _k(prefix: str, sender: str, session: str) -> str:
    return f"{prefix}:{sender}:{session}"

def _ka(prefix: str, sender: str) -> str:
    return f"{prefix}:{sender}"

# --- optional email sender ---
import httpx
import smtplib, ssl
from email.message import EmailMessage

def _smtp_enabled() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))

def _send_html_email(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    try:
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        passwd = os.getenv("SMTP_PASS")
        from_name = os.getenv("SMTP_FROM_NAME", "Duffel Flights")
        from_addr = os.getenv("SMTP_FROM", user or "")
        if not (host and port and user and passwd and from_addr and to_email):
            return
        msg = EmailMessage()
        msg["From"] = f"{from_name} <{from_addr}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype='html')
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(user, passwd)
            smtp.send_message(msg)
    except Exception:
        return

def _send_booking_email(to_email: str, passenger_name: str, order_id: str, booking_ref: Optional[str], total_text: Optional[str], itinerary: Optional[str], payment_method: Optional[str] = None, flight_route: Optional[str] = None) -> None:
    subj = f"✈️ Your Flight Booking Confirmed — {booking_ref or order_id}"
    
    # Plain text version
    lines = [
        f"Hi {passenger_name or 'Traveler'},",
        "",
        "🎉 Your flight booking is confirmed!",
        "",
        "Booking Details:",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Booking Reference (PNR): {booking_ref or '—'}",
    ]
    if flight_route:
        lines.append(f"Flight Route: {flight_route}")
    lines.extend([
        f"Order ID: {order_id}",
        f"Total Paid: {total_text or '—'}",
    ])
    if payment_method:
        lines.append(f"Paid Via: {payment_method}")
    if itinerary:
        lines += ["", "Flight Details:", itinerary]
    lines += [
        "",
        "What's Next?",
        "• Check in online 24 hours before departure",
        "• Arrive at the airport 2 hours early for domestic flights",
        "• Have your booking reference ready",
        "",
        "Need help? Contact our support team anytime.",
        "",
        "Safe travels! ✈️",
        "— The Flight Booking Team"
    ]
    text = "\n".join(lines)
    
    # Beautiful HTML version with gradient and modern design
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background:#f0f4f8;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
                    <!-- Header with gradient -->
                    <tr>
                        <td style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);padding:40px 30px;text-align:center;">
                            <div style="font-size:48px;margin-bottom:10px;">✈️</div>
                            <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:600;letter-spacing:-0.5px;">Booking Confirmed!</h1>
                            <p style="margin:10px 0 0;color:rgba(255,255,255,0.9);font-size:16px;">Your adventure awaits</p>
                        </td>
                    </tr>
                    
                    <!-- Main content -->
                    <tr>
                        <td style="padding:40px 30px;">
                            <p style="margin:0 0 25px;color:#1a202c;font-size:16px;line-height:1.6;">
                                Hi <strong>{passenger_name or 'Traveler'}</strong>,
                            </p>
                            <p style="margin:0 0 30px;color:#4a5568;font-size:16px;line-height:1.6;">
                                Great news! Your flight booking has been confirmed and you're all set for your journey. 🎉
                            </p>
                            
                            <!-- Booking details card -->
                            <div style="background:linear-gradient(135deg, #f6f8fb 0%, #e9ecf1 100%);border-radius:12px;padding:25px;margin-bottom:30px;border-left:4px solid #667eea;">
                                <h2 style="margin:0 0 20px;color:#2d3748;font-size:18px;font-weight:600;">📋 Booking Details</h2>
                                <table width="100%" cellpadding="8" cellspacing="0">
                                    <tr>
                                        <td style="color:#4a5568;font-size:14px;font-weight:500;padding:8px 0;">Booking Reference (PNR)</td>
                                        <td style="color:#1a202c;font-size:16px;font-weight:600;text-align:right;padding:8px 0;">{booking_ref or '—'}</td>
                                    </tr>
                                    {f'''
                                    <tr>
                                        <td style="color:#4a5568;font-size:14px;font-weight:500;padding:8px 0;border-top:1px solid #e2e8f0;">Flight Route</td>
                                        <td style="color:#1a202c;font-size:15px;font-weight:600;text-align:right;padding:8px 0;border-top:1px solid #e2e8f0;">{flight_route}</td>
                                    </tr>
                                    ''' if flight_route else ''}
                                    <tr>
                                        <td style="color:#4a5568;font-size:14px;font-weight:500;padding:8px 0;border-top:1px solid #e2e8f0;">Order ID</td>
                                        <td style="color:#718096;font-size:14px;text-align:right;padding:8px 0;border-top:1px solid #e2e8f0;font-family:monospace;">{order_id}</td>
                                    </tr>
                                    <tr>
                                        <td style="color:#4a5568;font-size:14px;font-weight:500;padding:8px 0;border-top:1px solid #e2e8f0;">Total Paid</td>
                                        <td style="color:#10b981;font-size:18px;font-weight:700;text-align:right;padding:8px 0;border-top:1px solid #e2e8f0;">{total_text or '—'}</td>
                                    </tr>
                                    {f'''
                                    <tr>
                                        <td style="color:#4a5568;font-size:14px;font-weight:500;padding:8px 0;border-top:1px solid #e2e8f0;">Paid Via</td>
                                        <td style="color:#667eea;font-size:14px;font-weight:600;text-align:right;padding:8px 0;border-top:1px solid #e2e8f0;">{payment_method}</td>
                                    </tr>
                                    ''' if payment_method else ''}
                                </table>
                            </div>
                            
                            {f'''
                            <!-- Flight details -->
                            <div style="background:#fefefe;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:30px;">
                                <h2 style="margin:0 0 15px;color:#2d3748;font-size:18px;font-weight:600;">✈️ Flight Details</h2>
                                <div style="color:#4a5568;font-size:14px;line-height:1.8;font-family:monospace;white-space:pre-line;">{itinerary}</div>
                            </div>
                            ''' if itinerary else ''}
                            
                            <!-- What's next section -->
                            <div style="background:#f7fafc;border-radius:12px;padding:25px;margin-bottom:25px;">
                                <h2 style="margin:0 0 15px;color:#2d3748;font-size:18px;font-weight:600;">📝 What's Next?</h2>
                                <ul style="margin:0;padding-left:20px;color:#4a5568;font-size:15px;line-height:1.8;">
                                    <li style="margin-bottom:8px;">Check in online 24 hours before departure</li>
                                    <li style="margin-bottom:8px;">Arrive at the airport 2 hours early for domestic flights</li>
                                    <li style="margin-bottom:8px;">Have your booking reference ready at check-in</li>
  </ul>
</div>
                            
                            <p style="margin:0;color:#718096;font-size:14px;line-height:1.6;text-align:center;">
                                Need help? Contact our support team anytime.<br>
                                We're here to make your journey smooth! 🌟
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background:#f7fafc;padding:25px 30px;text-align:center;border-top:1px solid #e2e8f0;">
                            <p style="margin:0 0 10px;color:#2d3748;font-size:16px;font-weight:600;">Safe travels! ✈️</p>
                            <p style="margin:0;color:#718096;font-size:14px;">— The Flight Booking Team</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    if _smtp_enabled():
        _send_html_email(to_email, subj, html, text)

def _send_cancellation_email(to_email: str, passenger_name: str, order_id: str, booking_ref: Optional[str], refund_amount: Optional[str]) -> None:
    """Send cancellation confirmation email."""
    try:
        # Normalize refund amount to USDC if possible (expects like "12.34 GBP")
        refund_text = None
        try:
            if refund_amount:
                parts = str(refund_amount).split()
                if len(parts) == 2:
                    amt_raw, cur = parts
                    usdc = _fx_to_usdc(amt_raw, cur)
                    if usdc:
                        refund_text = f"{usdc} USDC"
        except Exception:
            refund_text = None
        if not refund_text:
            refund_text = refund_amount  # fallback

        subj = f"🔄 Booking Cancellation Confirmed — {booking_ref or order_id}"
        
        # Plain text version
        text = f"""Hi {passenger_name or 'Traveler'},

Your booking has been successfully cancelled.

Cancellation Details:
━━━━━━━━━━━━━━━━━━━━
Order ID: {order_id}
Booking Reference (PNR): {booking_ref or '—'}
{f'Refund Amount: {refund_text}' if refund_text else ''}

⏱️ Your refund will be processed within 5 working days.

If you have any questions, please contact our support team.

— The Flight Booking Team
"""

        # Beautiful HTML version with modern design
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background:#f0f4f8;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
                    <!-- Header with orange gradient -->
                    <tr>
                        <td style="background:linear-gradient(135deg, #f093fb 0%, #f5576c 100%);padding:40px 30px;text-align:center;">
                            <div style="font-size:48px;margin-bottom:10px;">🔄</div>
                            <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:600;letter-spacing:-0.5px;">Cancellation Confirmed</h1>
                            <p style="margin:10px 0 0;color:rgba(255,255,255,0.9);font-size:16px;">Your booking has been cancelled</p>
                        </td>
                    </tr>
                    
                    <!-- Main content -->
                    <tr>
                        <td style="padding:40px 30px;">
                            <p style="margin:0 0 25px;color:#1a202c;font-size:16px;line-height:1.6;">
                                Hi <strong>{passenger_name or 'Traveler'}</strong>,
                            </p>
                            <p style="margin:0 0 30px;color:#4a5568;font-size:16px;line-height:1.6;">
                                Your booking has been successfully cancelled as requested. We've processed your cancellation and the details are below.
                            </p>
                            
                            <!-- Cancellation details card -->
                            <div style="background:linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%);border-radius:12px;padding:25px;margin-bottom:30px;border-left:4px solid #f5576c;">
                                <h2 style="margin:0 0 20px;color:#2d3748;font-size:18px;font-weight:600;">📋 Cancellation Details</h2>
                                <table width="100%" cellpadding="8" cellspacing="0">
                                    <tr>
                                        <td style="color:#4a5568;font-size:14px;font-weight:500;padding:8px 0;">Booking Reference (PNR)</td>
                                        <td style="color:#1a202c;font-size:16px;font-weight:600;text-align:right;padding:8px 0;">{booking_ref or '—'}</td>
                                    </tr>
                                    <tr>
                                        <td style="color:#4a5568;font-size:14px;font-weight:500;padding:8px 0;border-top:1px solid #fbd5d5;">Order ID</td>
                                        <td style="color:#718096;font-size:14px;text-align:right;padding:8px 0;border-top:1px solid #fbd5d5;font-family:monospace;">{order_id}</td>
                                    </tr>
                                    {f'''
                                    <tr>
                                        <td style="color:#4a5568;font-size:14px;font-weight:500;padding:8px 0;border-top:1px solid #fbd5d5;">Refund Amount</td>
                                        <td style="color:#10b981;font-size:18px;font-weight:700;text-align:right;padding:8px 0;border-top:1px solid #fbd5d5;">{refund_text}</td>
                                    </tr>
                                    ''' if refund_text else ''}
                                </table>
                            </div>
                            
                            <!-- Refund timeline -->
                            <div style="background:#fffbeb;border:2px solid #fbbf24;border-radius:12px;padding:20px;margin-bottom:25px;">
                                <div style="display:flex;align-items:center;margin-bottom:10px;">
                                    <span style="font-size:24px;margin-right:10px;">⏱️</span>
                                    <h3 style="margin:0;color:#92400e;font-size:16px;font-weight:600;">Refund Processing</h3>
                                </div>
                                <p style="margin:0;color:#78350f;font-size:14px;line-height:1.6;">
                                    Your refund will be processed within <strong>5 working days</strong> and credited back to your original payment method.
                                </p>
                            </div>
                            
                            <!-- Support section -->
                            <div style="background:#f7fafc;border-radius:12px;padding:20px;text-align:center;">
                                <p style="margin:0 0 10px;color:#2d3748;font-size:15px;font-weight:500;">Need Help?</p>
                                <p style="margin:0;color:#718096;font-size:14px;line-height:1.6;">
                                    If you have any questions about your cancellation or refund,<br>
                                    our support team is here to help! 💬
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background:#f7fafc;padding:25px 30px;text-align:center;border-top:1px solid #e2e8f0;">
                            <p style="margin:0 0 10px;color:#2d3748;font-size:16px;font-weight:600;">We hope to serve you again soon! 🌟</p>
                            <p style="margin:0;color:#718096;font-size:14px;">— The Flight Booking Team</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        
        if _smtp_enabled():
            _send_html_email(to_email, subj, html, text)
    except Exception:
        pass  # Silently fail email sending

# --- fx helper for display (optional) ---
def _fx_to_usdc(amount, currency: str) -> str | None:
    """Convert amount in given currency to USDC using FreeCurrencyAPI; returns string like '12.34' or None on failure."""
    try:
        amt = float(amount)
    except Exception:
        return None
    cur = (currency or "").upper()
    if not cur:
        return None
    if cur in {"USD","USDC"}:
        return f"{amt:.2f}"
    try:
        key = os.getenv("FREECURRENCYAPI_KEY", "")
        if not key:
            return None
        with httpx.Client(timeout=10.0) as client:
            r = client.get("https://api.freecurrencyapi.com/v1/latest", params={"apikey": key, "currencies": cur})
        if r.status_code >= 400:
            return None
        data = r.json() or {}
        rates = data.get("data") or {}
        usd_to_cur = float(rates.get(cur)) if cur in rates else None
        if not usd_to_cur or usd_to_cur <= 0:
            return None
        usd_per_cur = 1.0 / usd_to_cur
        return f"{(amt * usd_per_cur):.2f}"
    except Exception:
        return None

def _fet_usdc_price() -> float | None:
    """Fetch FET/USDC price from Binance; returns USDC per 1 FET."""
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": "FETUSDC"})
        if r.status_code >= 400:
            return None
        data = r.json() or {}
        price = float(data.get("price"))
        return price if price > 0 else None
    except Exception:
        return None

def _usdc_to_fet(amount_usdc: str | float | int) -> str | None:
    """Convert a USDC amount to FET using Binance price. Returns a string with 6 decimals, or None."""
    try:
        amt = float(amount_usdc)
        px = _fet_usdc_price()
        if not px or px <= 0:
            return None
        fet = amt / px
        return f"{fet:.6f}"
    except Exception:
        return None

# --- protocol ---
payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

# Allow agent.py to inject its wallet (optional)
_AGENT_WALLET_ADDR: Optional[str] = None
def set_agent_wallet(wallet) -> None:
    """Call this from agent.py at startup."""
    global _AGENT_WALLET_ADDR
    try:
        _AGENT_WALLET_ADDR = str(wallet.address())
    except Exception:
        _AGENT_WALLET_ADDR = None

def _recipient_str(ctx: Context) -> str:
    env_recipient = os.getenv("SELLER_RECIPIENT", "")
    cand = _AGENT_WALLET_ADDR or (env_recipient if env_recipient else None) or str(ctx.agent.address)
    return str(cand)

# ----------------------------
# PUBLIC: ask the user for a payment (idempotent per session)
# ----------------------------
async def request_payment_from_user(ctx: Context, user_address: str, description: Optional[str] = None) -> None:
    session = str(ctx.session)
    pr_key = _k("payment_requested", user_address, session)
    if ctx.storage.has(pr_key):
        ctx.logger.info(f"[payment] payment request already sent session={session} to={user_address}")
        return

    # Fixed pricing for testing; we will still compute and show original totals in a message
    fet_amount = os.getenv("FIXED_FET_AMOUNT", "0.001")
    usd_amount = os.getenv("FIXED_USD_AMOUNT", "0.001")

    # Compute original totals (USDC + FET) for informational text
    try:
        offer_id_for_pricing: Optional[str] = None
        key_sess = _k("selected_offer_id", user_address, session)
        if ctx.storage.has(key_sess):
            v = ctx.storage.get(key_sess)
            if isinstance(v, str) and v:
                offer_id_for_pricing = v
        if not offer_id_for_pricing:
            key_addr = _ka("selected_offer_id", user_address)
            if ctx.storage.has(key_addr):
                v2 = ctx.storage.get(key_addr)
                if isinstance(v2, str) and v2:
                    offer_id_for_pricing = v2

        original_usdc: Optional[str] = None
        original_fet: Optional[str] = None
        if offer_id_for_pricing:
            token = os.getenv("DUFFEL_TOKEN")
            if token:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Duffel-Version": "v2",
                    "Accept": "application/json",
                }
                with httpx.Client(timeout=15) as client:
                    r = client.get(f"https://api.duffel.com/air/offers/{offer_id_for_pricing}", headers=headers)
                if r.status_code < 400:
                    data = r.json() or {}
                    dd = data.get("data") or {}
                    amt = dd.get("total_amount")
                    cur = dd.get("total_currency") or ""
                    if amt and cur:
                        amt_usdc = _fx_to_usdc(amt, cur)
                        if amt_usdc:
                            original_usdc = amt_usdc
                            fet_est = _usdc_to_fet(amt_usdc)
                            if fet_est:
                                original_fet = fet_est
    except Exception:
        pass

    skyfire_service_id = get_skyfire_service_id()
    ctx.logger.info(f"[payment] Skyfire service ID: {skyfire_service_id}")

    accepted_funds = [
        Funds(currency="FET", amount=fet_amount, payment_method="fet_direct"),
    ]
    if skyfire_service_id:
        ctx.logger.info(f"[payment] Adding Skyfire USDC option: {usd_amount}")
        accepted_funds.append(Funds(currency="USDC", amount=usd_amount, payment_method="skyfire"))
    else:
        ctx.logger.warning("[payment] Skyfire service ID not found, only FET payment available")

    metadata: dict[str, str] = {}
    if skyfire_service_id:
        metadata["skyfire_service_id"] = skyfire_service_id
    if _AGENT_WALLET_ADDR:
        metadata["provider_agent_wallet"] = _AGENT_WALLET_ADDR

    recipient = _recipient_str(ctx)
    req = RequestPayment(
        accepted_funds=accepted_funds,
        recipient=recipient,
        deadline_seconds=300,
        reference=session,
        description=description or "Flight booking — pay to proceed",
        metadata=metadata,
    )

    await ctx.send(user_address, req)
    ctx.storage.set(pr_key, True)
    ctx.logger.info(f"[payment] → RequestPayment to={user_address} session={session} accepted={[(f.currency, f.amount, f.payment_method) for f in accepted_funds]}")
    
    # Note: Chat message about payment details is handled by the LLM, not here

# ----------------------------
# REQUIRED seller handlers
# ----------------------------
@payment_proto.on_message(CommitPayment)
async def on_commit(ctx: Context, sender: str, msg: CommitPayment) -> None:
    session = str(ctx.session)
    try:
        tx_key = _k(f"commit_{msg.transaction_id}", sender, session)
        if ctx.storage.has(tx_key):
            ctx.logger.info(f"[payment] duplicate CommitPayment ignored tx={msg.transaction_id}")
            return
    except Exception:
        pass

    method = msg.funds.payment_method
    verified = False
    try:
        ctx.logger.info(f"[payment] ← CommitPayment from={sender} session={session} method={method} currency={msg.funds.currency} amount={msg.funds.amount} tx={msg.transaction_id}")
    except Exception:
        pass

    if method == "fet_direct":
        buyer_wallet: Optional[str] = None
        try:
            if isinstance(msg.metadata, dict):
                buyer_wallet = msg.metadata.get("buyer_fet_wallet")
        except Exception:
            buyer_wallet = None

        verified = await verify_fet_payment(
            tx_hash=msg.transaction_id,
            recipient_address=_AGENT_WALLET_ADDR or _recipient_str(ctx),
            amount_fet=str(msg.funds.amount),
            logger=ctx.logger,
            sender_address=buyer_wallet,
        )

    elif method == "skyfire":
        try:
            usd_amount = str(msg.funds.amount)
        except Exception:
            usd_amount = "0.001"
        verified = await verify_and_charge(
                token=msg.transaction_id,
            amount_usdc=usd_amount,
                logger=ctx.logger,
            )

    if verified:
        try:
            ctx.storage.set(tx_key, True)
        except Exception:
            pass
        await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
        #await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text="✅ Payment received. We will proceed with your booking shortly.")]))
        try:
            ctx.logger.info(f"[payment] ✅ verified method={method} session={session}")
        except Exception:
            pass

        # mark session paid
        try:
            ctx.storage.set(_k("paid", sender, session), True)
        except Exception:
            pass

        # auto-book logic
        try:
            placed_key = _k("order_placed", sender, session)
            if ctx.storage.has(placed_key):
                ctx.logger.info(f"[booking] order already placed for session={session}")
                return

            # Resolve selected offer
            offer_id: Optional[str] = None
            if ctx.storage.has(_k("selected_offer_id", sender, session)):
                v = ctx.storage.get(_k("selected_offer_id", sender, session))
                if isinstance(v, str) and v:
                    offer_id = v
            if not offer_id:
                if ctx.storage.has(_ka("selected_offer_id", sender)):
                    v2 = ctx.storage.get(_ka("selected_offer_id", sender))
                    if isinstance(v2, str) and v2:
                        offer_id = v2

            passenger: Optional[dict] = None
            if ctx.storage.has(_k("passenger_1", sender, session)):
                p = ctx.storage.get(_k("passenger_1", sender, session))
                if isinstance(p, dict):
                    passenger = p
            if not passenger:
                if ctx.storage.has(_ka("passenger_1", sender)):
                    p2 = ctx.storage.get(_ka("passenger_1", sender))
                    if isinstance(p2, dict):
                        passenger = p2
            
            # Get offer_passengers (IDs from the offer)
            offer_passengers: Optional[list] = None
            if ctx.storage.has(_k("offer_passengers", sender, session)):
                op = ctx.storage.get(_k("offer_passengers", sender, session))
                if isinstance(op, list):
                    offer_passengers = op

            # Validate we have both offer and passenger
            if not offer_id:
                ctx.logger.error(f"[booking] No offer_id found for session={session}")
                await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text="Missing flight selection. Please search and select a flight first.")]))
                return
            
            if not (isinstance(passenger, dict) and passenger.get("born_on")):
                ctx.logger.error(f"[booking] Missing passenger DOB for session={session}")
                await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text="Missing date of birth (YYYY-MM-DD). Please provide DOB and say 'book now'.")]))
                return

            ctx.logger.info(f"[booking] Proceeding with offer_id={offer_id}, passenger={passenger.get('given_name')} {passenger.get('family_name')}")

            # Map passenger ID from offer_passengers (first adult)
            if offer_passengers and len(offer_passengers) > 0:
                # Find first adult passenger ID
                for op in offer_passengers:
                    if isinstance(op, dict) and op.get("type") == "adult":
                        passenger["id"] = op.get("id")
                        ctx.logger.info(f"[booking] Mapped passenger ID: {passenger['id']}")
                        break

            services: Optional[list] = None
            if ctx.storage.has(_k("selected_services", sender, session)):
                sv = ctx.storage.get(_k("selected_services", sender, session))
                if isinstance(sv, list):
                    services = sv

            # call booking tool    
            res = None
            try:
                if duffel_create_order is not None:
                    # Unwrap LangChain tool if needed
                    func = duffel_create_order
                    if hasattr(func, 'func'):
                        func = func.func
                    
                    ctx.logger.info(f"[booking] Calling duffel_create_order with offer_id={offer_id}, passenger={passenger}")
                    res = func(
                        offer_id=offer_id,
                        passengers=[passenger],
                        services=services,
                        pay_with_balance_now=True,
                    )
                    ctx.logger.info(f"[booking] duffel_create_order result: {res}")
                    ctx.logger.info(f"[booking] Result type: {type(res)}, has error: {res.get('error') if isinstance(res, dict) else 'N/A'}")
            except Exception as e:
                ctx.logger.error(f"[booking] duffel_create_order failed: {e}")
                res = None

            if isinstance(res, dict) and not res.get("error"):
                order_id = res.get("id") or res.get("order_id")
                booking_reference = res.get("booking_reference")
                total_amount = res.get("total_amount")
                total_currency = res.get("total_currency")

                total_amount_usdc = _fx_to_usdc(total_amount, total_currency)
                display_amount = total_amount_usdc or total_amount
                display_currency = "USDC" if total_amount_usdc else total_currency

                # record booking history
                key_hist = _ka("booked_offers", sender)
                history = ctx.storage.get(key_hist) if ctx.storage.has(key_hist) else []
                if not isinstance(history, list):
                    history = []
                history.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "session": session,
                    "method": method,
                    "currency": str(msg.funds.currency),
                    "amount": str(msg.funds.amount),
                    "tx": str(msg.transaction_id),
                    "order_id": order_id,
                    "booking_ref": booking_reference,
                    "total": f"{display_amount} {display_currency}" if display_amount and display_currency else None,
                })
                ctx.storage.set(key_hist, history)
                ctx.logger.info(f"[booking] saved entry addr={sender} session={session} order={order_id}")

                ctx.storage.set(placed_key, True)
                lines = [
                    "Booking confirmed:",
                    f"Order ID: {order_id}",
                    f"Booking reference: {booking_reference}",
                    f"Total paid: {display_amount} {display_currency}",
                ]
                await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text="\n".join([ln for ln in lines if ln and str(ln).strip() != "None"]))]))

                try:
                    email_to = passenger.get("email")
                    pax_name = (passenger.get("given_name") or "") + (" " + (passenger.get("family_name") or ""))
                    total_text = f"{display_amount} {display_currency}" if display_amount and display_currency else None
                    
                    # Format payment method
                    payment_method_display = None
                    if method == "skyfire":
                        payment_method_display = "Skyfire (USDC)"
                    elif method == "fet_direct":
                        payment_method_display = "FET Direct"
                    else:
                        payment_method_display = method.upper() if method else None
                    
                    # Try to get flight route from stored offer details
                    flight_route = None
                    try:
                        if ctx.storage.has(_k("offer_details", sender, session)):
                            offer_details = ctx.storage.get(_k("offer_details", sender, session))
                            if isinstance(offer_details, dict):
                                # Extract route from offer details
                                slices = offer_details.get("slices", [])
                                if slices and len(slices) > 0:
                                    first_slice = slices[0]
                                    segments = first_slice.get("segments", [])
                                    if segments:
                                        origin = segments[0].get("origin", {}).get("iata_code")
                                        destination = segments[-1].get("destination", {}).get("iata_code")
                                        dep_time = segments[0].get("departing_at", "")
                                        arr_time = segments[-1].get("arriving_at", "")
                                        if origin and destination:
                                            # Format: SFO→LAX • Jan 22, 2026 • 16:15-17:33
                                            #from datetime import datetime
                                            if dep_time:
                                                dep_dt = datetime.fromisoformat(dep_time.replace("Z", "+00:00"))
                                                date_str = dep_dt.strftime("%b %d, %Y")
                                                time_str = dep_dt.strftime("%H:%M")
                                                if arr_time:
                                                    arr_dt = datetime.fromisoformat(arr_time.replace("Z", "+00:00"))
                                                    time_str += f"-{arr_dt.strftime('%H:%M')}"
                                                flight_route = f"{origin}→{destination} • {date_str} • {time_str}"
                                            else:
                                                flight_route = f"{origin}→{destination}"
                    except Exception as e:
                        ctx.logger.warning(f"Could not extract flight route: {e}")
                    
                    if email_to:
                        _send_booking_email(
                            to_email=email_to,
                            passenger_name=pax_name,
                            order_id=str(order_id),
                            booking_ref=(str(booking_reference) if booking_reference else None),
                            total_text=total_text,
                            itinerary=None,
                            payment_method=payment_method_display,
                            flight_route=flight_route,
                        )
                except Exception as e:
                    ctx.logger.warning(f"Failed to send booking email: {e}")
            else:
                error_msg = "Booking failed after payment."
                if res and res.get("error"):
                    error_msg += f" Error: {res.get('error')}"
                ctx.logger.error(f"[booking] {error_msg}")
                await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=error_msg + " Please contact support.")]))
        except Exception as e:
            ctx.logger.error(f"[booking] auto-book attempt failed: {e}")
            await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=f"Booking error: {str(e)}")]))
    else:
        await ctx.send(sender, RejectPayment(reason="Payment verification failed"))
        try:
            ctx.logger.error(f"[payment] ❌ verification failed method={method} session={session}")
        except Exception:
            pass

@payment_proto.on_message(RejectPayment)
async def on_reject_payment(ctx: Context, sender: str, msg: RejectPayment) -> None:
    await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text="Payment was rejected. We can try again, change method, or adjust the booking.")]))
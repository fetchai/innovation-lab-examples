"""Skyfire payment integration matching the seller example semantics."""

import logging
import os
from typing import Any, Dict, Optional

import aiohttp
from jose import JWTError, jwk, jwt

from uagents_adapter.a2a_outbound.ap2.artifacts import PaymentResponse

logger = logging.getLogger(__name__)

JWKS_URL = os.getenv("JWKS_URL")
JWT_ISSUER = os.getenv("JWT_ISSUER")
JWT_AUDIENCE = os.getenv("SELLER_ACCOUNT_ID")
JWT_ALGORITHM = "ES256"

SKYFIRE_TOKENS_CHARGE_API_URL = os.getenv("SKYFIRE_TOKENS_CHARGE_API_URL") or os.getenv(
    "SKYFIRE_TOKENS_API_URL"
)
SELLER_SERVICE_ID = os.getenv("SELLER_SERVICE_ID")
SELLER_SKYFIRE_API_KEY = os.getenv("SELLER_SKYFIRE_API_KEY")


class SkyfirePaymentError(Exception):
    pass


async def get_jwks_from_url(jwks_url: str) -> Dict[str, Any]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(jwks_url) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        raise SkyfirePaymentError(f"Failed to fetch JWKS: {e}")


def get_signing_key(jwks_data: Dict[str, Any], kid: str):
    for key in jwks_data.get("keys", []):
        if key.get("kid") == kid:
            return jwk.construct(key, algorithm=JWT_ALGORITHM)
    raise SkyfirePaymentError(f"Unable to find key with kid: {kid}")


async def verify_skyfire_token(skyfire_token: str) -> Dict[str, Any]:
    try:
        unverified_header = jwt.get_unverified_header(skyfire_token)
        kid = unverified_header.get("kid")
        if not kid:
            raise SkyfirePaymentError("Token header missing 'kid' field")
        jwks_data = await get_jwks_from_url(JWKS_URL)
        signing_key = get_signing_key(jwks_data, kid)
        claims = jwt.decode(
            skyfire_token,
            signing_key,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        if claims.get("ssi") != SELLER_SERVICE_ID:
            raise SkyfirePaymentError(
                f"Token is not issued for this service: {SELLER_SERVICE_ID}"
            )
    except JWTError as err:
        raise SkyfirePaymentError(f"JWT verification failed: {err}")
    except Exception as err:
        raise SkyfirePaymentError(f"Token verification failed: {err}")
    try:
        decoded_token = jwt.get_unverified_claims(skyfire_token)
        return decoded_token
    except JWTError as err:
        logger.warning(f"Error decoding token: {err}")
        return {}


async def charge_skyfire_token(token: str, amount_to_charge: str) -> Dict[str, Any]:
    try:
        if not SKYFIRE_TOKENS_CHARGE_API_URL or not isinstance(
            SKYFIRE_TOKENS_CHARGE_API_URL, str
        ):
            raise SkyfirePaymentError(
                "Skyfire charge URL is not configured. Set SKYFIRE_TOKENS_CHARGE_API_URL (or SKYFIRE_TOKENS_API_URL)."
            )
        if not SELLER_SKYFIRE_API_KEY:
            raise SkyfirePaymentError(
                "Skyfire API key is not configured. Set SELLER_SKYFIRE_API_KEY."
            )
        async with aiohttp.ClientSession() as session:
            payload = {"token": token, "chargeAmount": amount_to_charge}
            async with session.post(
                SKYFIRE_TOKENS_CHARGE_API_URL,
                json=payload,
                headers={
                    "skyfire-api-key": SELLER_SKYFIRE_API_KEY,
                    "skyfire-api-version": "2",
                    "content-type": "application/json",
                },
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return {
                    "amountCharged": data["amountCharged"],
                    "remainingBalance": data["remainingBalance"],
                }
    except aiohttp.ClientError as err:
        raise SkyfirePaymentError(f"Token charging failed: {err}")
    except Exception as err:
        raise SkyfirePaymentError(f"Skyfire charge error: {err}")


async def process_skyfire_payment(token: str, expected_amount: str) -> Dict[str, Any]:
    try:
        logger.info(f"Verifying Skyfire token for amount: ${expected_amount}")
        claims = await verify_skyfire_token(token)
        logger.info("Token verified, proceeding to charge")
        charge_result = await charge_skyfire_token(token, expected_amount)
        return {
            "success": True,
            "transaction_id": token,
            "amount_charged": charge_result["amountCharged"],
            "remaining_balance": charge_result["remainingBalance"],
            "claims": claims,
        }
    except SkyfirePaymentError as e:
        logger.error(f"Skyfire payment processing failed: {e}")
        return {"success": False, "transaction_id": token, "error": str(e)}


def detect_skyfire_token(payment_response: PaymentResponse) -> Optional[str]:
    token_locations = ["transaction_token", "token"]
    for location in token_locations:
        if location in payment_response.details:
            token = payment_response.details[location]
            if isinstance(token, str):
                return token
    return None


def is_skyfire_payment(payment_response: PaymentResponse) -> bool:
    return (payment_response.method_name or "").lower() == "skyfire"



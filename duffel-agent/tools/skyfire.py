# tools/skyfire.py
"""
Skyfire token verification + charging helpers.

Env (set via .env):
  SKYFIRE_ENV=qa|test|sandbox|production
  JWKS_URL, JWT_ISSUER, SKYFIRE_TOKENS_API_URL   # optional; derived from SKYFIRE_ENV if unset
  SELLER_ACCOUNT_ID                               # audience to verify
  SELLER_SERVICE_ID                               # expected `ssi` claim
  SELLER_SKYFIRE_API_KEY (or SKYFIRE_API_KEY)     # server-side API key for charging

API:
  - get_skyfire_service_id() -> Optional[str]
  - get_seller_account_id()  -> Optional[str]
  - verify_token_claims(token, logger) -> bool
  - charge_token(token, amount_usdc, logger, idempotency_key=None) -> bool
  - verify_and_charge(token, amount_usdc, logger, idempotency_key=None) -> bool
"""

from __future__ import annotations
import os
import uuid
from typing import Any, Optional

import aiohttp
from jose import JWTError, jwk, jwt

# -------- Environment & defaults --------

_SKYFIRE_ENV = (os.getenv("SKYFIRE_ENV") or "qa").lower()
if _SKYFIRE_ENV in {"qa", "test", "sandbox"}:
    _DEFAULT_APP_BASE = "https://app-qa.skyfire.xyz"
    _DEFAULT_API_BASE = "https://api-qa.skyfire.xyz"
else:
    _DEFAULT_APP_BASE = "https://app.skyfire.xyz"
    _DEFAULT_API_BASE = "https://api.skyfire.xyz"

JWKS_URL = os.getenv("JWKS_URL", f"{_DEFAULT_APP_BASE}/.well-known/jwks.json")
JWT_ISSUER = os.getenv("JWT_ISSUER", f"{_DEFAULT_APP_BASE}")
SKYFIRE_TOKENS_API_URL = os.getenv("SKYFIRE_TOKENS_API_URL", f"{_DEFAULT_API_BASE}/api/v1/tokens/charge")

SELLER_ACCOUNT_ID = os.getenv("SELLER_ACCOUNT_ID", "")  # used as JWT audience
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", SELLER_ACCOUNT_ID or "")

SELLER_SERVICE_ID = os.getenv("SELLER_SERVICE_ID", "")
SKYFIRE_API_KEY = os.getenv("SELLER_SKYFIRE_API_KEY") or os.getenv("SKYFIRE_API_KEY")

JWT_ALGORITHM = "ES256"


# -------- Helpers to expose configured IDs --------

def get_skyfire_service_id() -> Optional[str]:
    return SELLER_SERVICE_ID or None

def get_seller_account_id() -> Optional[str]:
    return SELLER_ACCOUNT_ID or (JWT_AUDIENCE or None)


# -------- Internal JWKS helpers --------

async def _fetch_json(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    async with session.get(url, timeout=20) as resp:
        resp.raise_for_status()
        return await resp.json()

def _jwk_by_kid(jwks: dict[str, Any], kid: str):
    for k in jwks.get("keys", []) or []:
        if k.get("kid") == kid:
            return jwk.construct(k, algorithm=JWT_ALGORITHM)
    raise JWTError(f"JWKS key not found for kid={kid!r}")


# -------- Public verification & charging --------

async def verify_token_claims(token: str, logger) -> bool:
    """
    Verify the Skyfire buyer token:
      - Signature via JWKS (ES256)
      - issuer matches JWT_ISSUER
      - audience matches SELLER_ACCOUNT_ID/JWT_AUDIENCE (if configured)
      - claims['ssi'] equals SELLER_SERVICE_ID (if configured)
    """
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise JWTError("Missing 'kid' in token header")

        async with aiohttp.ClientSession() as session:
            jwks = await _fetch_json(session, JWKS_URL)

        key = _jwk_by_kid(jwks, kid)

        audience = JWT_AUDIENCE or None
        claims = jwt.decode(
            token,
            key,
            algorithms=[JWT_ALGORITHM],
            audience=audience,
            issuer=JWT_ISSUER,
            options={"verify_aud": bool(audience)},
        )

        if SELLER_SERVICE_ID:
            ssi = claims.get("ssi")
            if ssi != SELLER_SERVICE_ID:
                raise JWTError(f"Service mismatch: token.ssi={ssi}, expected={SELLER_SERVICE_ID}")

        logger.info("Skyfire token verified OK")
        return True

    except JWTError as e:
        logger.error(f"Skyfire token verification failed: {e}")
        return False
    except aiohttp.ClientError as e:
        logger.error(f"JWKS fetch error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected verification error: {e}")
        return False


async def charge_token(
    token: str,
    amount_usdc: str,
    logger,
    *,
    idempotency_key: Optional[str] = None,
) -> bool:
    """
    Charge a verified Skyfire token.
    amount_usdc: string decimal (e.g. "12.34")
    """
    if not SKYFIRE_API_KEY:
        logger.error("SELLER_SKYFIRE_API_KEY / SKYFIRE_API_KEY is not set")
        return False

    payload = {"token": token, "chargeAmount": str(amount_usdc)}
    headers = {
        "skyfire-api-key": SKYFIRE_API_KEY,
        "skyfire-api-version": "2",
        "content-type": "application/json",
    }
    if idempotency_key is None:
        idempotency_key = str(uuid.uuid4())
    headers["x-idempotency-key"] = idempotency_key

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                SKYFIRE_TOKENS_API_URL, json=payload, headers=headers, timeout=30
            ) as resp:
                body = await resp.text()
                logger.info(
                    f"Skyfire charge status={resp.status} idempotency={idempotency_key} "
                    f"endpoint={SKYFIRE_TOKENS_API_URL} body={body[:300]}"
                )
                resp.raise_for_status()
                return True

    except aiohttp.ClientResponseError as e:
        logger.error(f"Skyfire charge failed: {e.status} {e.message}")
        return False
    except aiohttp.ClientError as e:
        logger.error(f"Skyfire charge network error: {e}")
        return False
    except Exception as e:
        logger.error(f"Skyfire charge unexpected error: {e}")
        return False


async def verify_and_charge(
    token: str,
    amount_usdc: str,
    logger,
    *,
    idempotency_key: Optional[str] = None,
) -> bool:
    """
    Convenience: verify claims, then charge the token.
    """
    if not (SELLER_SERVICE_ID and (SELLER_ACCOUNT_ID or JWT_AUDIENCE)):
        logger.error("Skyfire seller variables not configured (service/account)")
        return False

    ok = await verify_token_claims(token, logger)
    if not ok:
        return False

    return await charge_token(token, amount_usdc, logger, idempotency_key=idempotency_key)
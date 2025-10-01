import logging
import os
from typing import Optional, Any

import aiohttp
from jose import JWTError, jwk, jwt

# Production-only endpoints
APP_BASE = "https://app.skyfire.xyz"
API_BASE = "https://api.skyfire.xyz"

# JWKS/JWT config (prod defaults)
JWKS_URL = os.getenv("JWKS_URL") or f"{APP_BASE}/.well-known/jwks.json"
# Normalize issuer to avoid trailing-slash mismatches
JWT_ISSUER = (os.getenv("JWT_ISSUER") or APP_BASE).rstrip("/")
# Prefer explicit audience, then seller account id, then legacy account id
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE") or os.getenv("SELLER_ACCOUNT_ID") or os.getenv("SKYFIRE_ACCOUNT_ID", "")
JWT_ALGORITHM = "ES256"

# Charge API (provider flow)
SKYFIRE_TOKENS_API_URL = os.getenv("SKYFIRE_TOKENS_API_URL", f"{API_BASE}/api/v1/tokens/charge")

# Prefer SELLER_* variables if provided; fallback to legacy names
SKYFIRE_API_KEY = os.getenv("SKYFIRE_API_KEY") or os.getenv("SELLER_SKYFIRE_API_KEY")
SKYFIRE_SERVICE_ID = os.getenv("SKYFIRE_SERVICE_ID") or os.getenv("SELLER_SERVICE_ID")
SELLER_ACCOUNT_ID = os.getenv("SELLER_ACCOUNT_ID")


async def get_jwks_from_url(jwks_url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(jwks_url) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        raise Exception(f"Failed to fetch JWKS: {e}")


def get_signing_key(jwks_data: dict[str, Any], kid: str):
    for key in jwks_data.get("keys", []):
        if key.get("kid") == kid:
            return jwk.construct(key, algorithm=JWT_ALGORITHM)
    raise Exception(f"Unable to find key with kid: {kid}")


async def verify_token_claims(skyfire_token: str, logger: logging.Logger) -> bool:
    try:
        unverified_header = jwt.get_unverified_header(skyfire_token)
        kid = unverified_header.get("kid")
        if not kid:
            raise JWTError("Token header missing 'kid'")
        jwks_data = await get_jwks_from_url(JWKS_URL)
        signing_key = get_signing_key(jwks_data, kid)
        audience = JWT_AUDIENCE or SELLER_ACCOUNT_ID or ""
        claims = jwt.decode(
            skyfire_token,
            signing_key,
            algorithms=[JWT_ALGORITHM],
            audience=audience,
            issuer=JWT_ISSUER,
        )
        ssi = claims.get("ssi")
        if SKYFIRE_SERVICE_ID and ssi != SKYFIRE_SERVICE_ID:
            raise JWTError(f"Token is not issued for this service: {SKYFIRE_SERVICE_ID}")
        return True
    except JWTError as err:
        logger.error(f"Skyfire token JWT verification failed: {err}")
        return False
    except Exception as err:
        logger.error(f"Skyfire token verification error: {err}")
        return False


async def charge_token(token: str, amount_to_charge: str, logger: logging.Logger) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"token": token, "chargeAmount": amount_to_charge}
            async with session.post(
                SKYFIRE_TOKENS_API_URL,
                json=payload,
                headers={
                    "skyfire-api-key": SKYFIRE_API_KEY or "",
                    "skyfire-api-version": "2",
                    "content-type": "application/json",
                },
            ) as resp:
                logger.info(f"Skyfire charge API status: {resp.status}")
                body = await resp.text()
                logger.info(f"Skyfire charge API body: {body[:500]}")
                resp.raise_for_status()
                return True
    except aiohttp.ClientError as err:
        logger.error(f"Skyfire charge error: {err}")
        return False


async def verify_and_charge(token: str, amount_usdc: str, logger: logging.Logger) -> bool:
    if not (SKYFIRE_API_KEY and SKYFIRE_SERVICE_ID and (SELLER_ACCOUNT_ID or JWT_AUDIENCE)):
        logger.error("Skyfire seller variables not configured")
        return False
    ok = await verify_token_claims(token, logger)
    if not ok:
        return False
    return await charge_token(token, amount_usdc, logger)


def get_skyfire_service_id() -> Optional[str]:
    return SKYFIRE_SERVICE_ID



"""Google Sheets integration with per-user OAuth device flow."""

import json
import os
import time
import requests
from datetime import datetime
from typing import Any

import gspread
import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

DEVICE_CODE_ENDPOINT = "https://oauth2.googleapis.com/device/code"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

TOKEN_STORE_FILE = os.getenv("GOOGLE_OAUTH_TOKEN_STORE_FILE", "google_user_tokens.json")
DEVICE_STORE_FILE = os.getenv("GOOGLE_OAUTH_DEVICE_STORE_FILE", "google_device_flows.json")


class GoogleAuthRequiredError(RuntimeError):
    """Raised when a user must complete Google OAuth before sheet creation."""


def _load_json_file(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json_file(path: str, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _post_form(url: str, data: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(url, data=data, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as exc:
        body = exc.response.text
        try:
            parsed = exc.response.json()
        except Exception:
            parsed = {}
        if "error" not in parsed:
            parsed["error"] = f"http_{exc.response.status_code}"
        if "error_description" not in parsed and body:
            parsed["error_description"] = body
        return parsed


def _load_oauth_client_credentials() -> tuple[str, str]:
    raw = os.getenv("GOOGLE_OAUTH_CLIENT_JSON", "").strip()
    file_path = os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "").strip()

    if raw:
        config = json.loads(raw)
    elif file_path:
        if not os.path.exists(file_path):
            raise RuntimeError(f"GOOGLE_OAUTH_CLIENT_FILE does not exist: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        raise RuntimeError(
            "Missing OAuth client config. Set GOOGLE_OAUTH_CLIENT_JSON "
            "or GOOGLE_OAUTH_CLIENT_FILE."
        )

    section = config.get("installed") or config.get("web") or config
    client_id = str(section.get("client_id", "")).strip()
    client_secret = str(section.get("client_secret", "")).strip()
    if not client_id:
        raise RuntimeError("OAuth client config missing client_id.")
    return client_id, client_secret


def _start_device_flow(client_id: str) -> dict[str, Any]:
    response = _post_form(
        DEVICE_CODE_ENDPOINT,
        {
            "client_id": client_id,
            "scope": " ".join(SCOPES),
        },
    )

    if "error" in response:
        description = response.get("error_description", "")
        raise RuntimeError(f"Google device authorization failed: {response['error']} {description}")

    now = int(time.time())
    expires_in = int(response.get("expires_in", 900))
    return {
        "device_code": response["device_code"],
        "user_code": response["user_code"],
        "verification_url": response.get("verification_url")
        or response.get("verification_uri")
        or "https://www.google.com/device",
        "expires_at": now + expires_in,
        "interval": int(response.get("interval", 5)),
        "expires_in": expires_in,
    }


def _poll_device_flow(client_id: str, client_secret: str, device_code: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "client_id": client_id,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }
    if client_secret:
        payload["client_secret"] = client_secret
    return _post_form(TOKEN_ENDPOINT, payload)


def _build_auth_required_message(flow: dict[str, Any]) -> str:
    expires_at = int(flow.get("expires_at", int(time.time())))
    minutes = max(1, int((expires_at - int(time.time())) / 60))
    return (
        "Google authorization required for sheet creation.\n"
        f"1) Open: {flow.get('verification_url', 'https://www.google.com/device')}\n"
        f"2) Enter code: {flow.get('user_code', '')}\n"
        "3) Approve Drive/Sheets access\n"
        "4) Re-run the same search request\n"
        f"Code expires in about {minutes} minute(s)."
    )


def _credential_info_from_token_response(
    token_response: dict[str, Any],
    client_id: str,
    client_secret: str,
    previous_refresh_token: str = "",
) -> dict[str, Any]:
    refresh_token = token_response.get("refresh_token") or previous_refresh_token
    return {
        "token": token_response.get("access_token", ""),
        "refresh_token": refresh_token,
        "token_uri": TOKEN_ENDPOINT,
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES,
    }


def _get_user_credentials(user_id: str) -> Credentials:
    client_id, client_secret = _load_oauth_client_credentials()

    token_store = _load_json_file(TOKEN_STORE_FILE)
    saved_token_info = token_store.get(user_id)
    if saved_token_info:
        creds = Credentials.from_authorized_user_info(saved_token_info, SCOPES)
        if not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_store[user_id] = json.loads(creds.to_json())
            _save_json_file(TOKEN_STORE_FILE, token_store)
        if creds.valid:
            return creds
        token_store.pop(user_id, None)
        _save_json_file(TOKEN_STORE_FILE, token_store)

    device_store = _load_json_file(DEVICE_STORE_FILE)
    flow = device_store.get(user_id)
    now = int(time.time())

    if flow and now >= int(flow.get("expires_at", 0)):
        device_store.pop(user_id, None)
        _save_json_file(DEVICE_STORE_FILE, device_store)
        flow = None

    if not flow:
        flow = _start_device_flow(client_id)
        device_store[user_id] = flow
        _save_json_file(DEVICE_STORE_FILE, device_store)
        raise GoogleAuthRequiredError(_build_auth_required_message(flow))

    token_response = _poll_device_flow(client_id, client_secret, flow["device_code"])
    error = token_response.get("error")
    if error:
        if error in {"authorization_pending", "slow_down"}:
            if error == "slow_down":
                flow["interval"] = int(flow.get("interval", 5)) + 5
                device_store[user_id] = flow
                _save_json_file(DEVICE_STORE_FILE, device_store)
            raise GoogleAuthRequiredError(_build_auth_required_message(flow))

        if error in {"access_denied", "expired_token", "invalid_grant"}:
            device_store.pop(user_id, None)
            _save_json_file(DEVICE_STORE_FILE, device_store)
            new_flow = _start_device_flow(client_id)
            device_store[user_id] = new_flow
            _save_json_file(DEVICE_STORE_FILE, device_store)
            raise GoogleAuthRequiredError(
                "Google authorization was denied or expired.\n"
                + _build_auth_required_message(new_flow)
            )

        description = token_response.get("error_description", "")
        raise RuntimeError(f"Google OAuth token exchange failed: {error} {description}")

    previous_refresh_token = ""
    if saved_token_info:
        previous_refresh_token = saved_token_info.get("refresh_token", "")

    token_store[user_id] = _credential_info_from_token_response(
        token_response,
        client_id,
        client_secret,
        previous_refresh_token=previous_refresh_token,
    )
    _save_json_file(TOKEN_STORE_FILE, token_store)

    device_store.pop(user_id, None)
    _save_json_file(DEVICE_STORE_FILE, device_store)

    creds = Credentials.from_authorized_user_info(token_store[user_id], SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_store[user_id] = json.loads(creds.to_json())
        _save_json_file(TOKEN_STORE_FILE, token_store)

    if not creds.valid:
        raise RuntimeError("Google OAuth completed but credentials are invalid.")
    return creds


def get_google_auth_message(user_id: str) -> str:
    """Return either connected status or auth steps for this user."""
    try:
        _get_user_credentials(user_id)
        return "Google is already connected for this user."
    except GoogleAuthRequiredError as exc:
        return str(exc)


def get_gspread_client_for_user(user_id: str) -> gspread.Client:
    """Authenticate to Google as a specific user and return gspread client."""
    creds = _get_user_credentials(user_id)
    return gspread.authorize(creds)


def create_listings_sheet(
    df: pd.DataFrame,
    location: str,
    listing_type: str,
    user_id: str,
) -> str:
    """Create a new Google Sheet under the authenticated user's Drive."""
    client = get_gspread_client_for_user(user_id)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    sheet_title = f"Real Estate: {location} ({listing_type}) - {timestamp}"
    spreadsheet = client.create(sheet_title)

    spreadsheet.share(None, perm_type="anyone", role="reader")

    share_email = os.getenv("GOOGLE_SHEET_SHARE_EMAIL", "").strip()
    if share_email:
        try:
            spreadsheet.share(share_email, perm_type="user", role="writer")
        except Exception:
            pass

    worksheet = spreadsheet.sheet1
    worksheet.update_title("Listings")

    if df.empty:
        worksheet.update("A1", [["No listings found matching your criteria."]])
        return spreadsheet.url

    headers = list(df.columns)
    worksheet.update("A1", [headers])
    worksheet.format(
        "1:1",
        {
            "backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.58},
            "textFormat": {
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                "bold": True,
                "fontSize": 11,
            },
            "horizontalAlignment": "CENTER",
        },
    )

    rows = df.fillna("N/A").values.tolist()
    worksheet.update("A2", rows)

    num_rows = len(rows) + 1
    price_col_idx = headers.index("Price ($)") + 1 if "Price ($)" in headers else None
    worksheet.columns_auto_resize(0, len(headers))

    summary = f"Found {len(df)} properties in {location} | Generated {timestamp}"
    worksheet.insert_row([summary], index=1)

    if price_col_idx:
        price_col_letter = chr(64 + price_col_idx)
        worksheet.format(
            f"{price_col_letter}3:{price_col_letter}{num_rows + 1}",
            {"numberFormat": {"type": "NUMBER", "pattern": "$#,##0"}},
        )
    worksheet.format(
        "A1",
        {
            "textFormat": {"italic": True, "fontSize": 10},
            "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
        },
    )

    end_col_letter = chr(64 + len(headers))
    worksheet.merge_cells(f"A1:{end_col_letter}1")

    print(f"Google Sheet created: {spreadsheet.url}")
    return spreadsheet.url


if __name__ == "__main__":
    uid = "local_test_user"
    print("Google auth status:")
    print(get_google_auth_message(uid))

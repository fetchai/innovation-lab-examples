"""
GCS Storage utility for uploading media files.
Returns public URLs. Supports base64 credentials (Agentverse) and ADC (local).
"""

import os  # noqa: F401
import base64
import json
from typing import Optional
from google.cloud import storage
from google.oauth2 import service_account

from config import GCS_BUCKET_NAME, GOOGLE_CLOUD_PROJECT, GCS_CREDENTIALS_BASE64

# ── Initialise GCS client ───────────────────────────────────────
_client: Optional[storage.Client] = None
_bucket = None

if GCS_BUCKET_NAME and GOOGLE_CLOUD_PROJECT:
    try:
        if GCS_CREDENTIALS_BASE64:
            creds_json = base64.b64decode(GCS_CREDENTIALS_BASE64).decode("utf-8")
            credentials = service_account.Credentials.from_service_account_info(
                json.loads(creds_json)
            )
            _client = storage.Client(
                credentials=credentials, project=GOOGLE_CLOUD_PROJECT
            )
        else:
            _client = storage.Client(project=GOOGLE_CLOUD_PROJECT)

        _bucket = _client.bucket(GCS_BUCKET_NAME)
        print(f"✅ GCS ready: bucket={GCS_BUCKET_NAME}")
    except Exception as e:
        print(f"❌ GCS init failed: {e}")


def upload_to_storage(
    file_data: bytes, filename: str, content_type: str = "video/mp4"
) -> str:
    """Upload bytes to GCS, return public URL."""
    if not _client or not _bucket:
        raise ValueError(
            "GCS not configured. Set GCS_BUCKET_NAME and GOOGLE_CLOUD_PROJECT."
        )

    blob = _bucket.blob(f"videos/{filename}")
    blob.upload_from_string(file_data, content_type=content_type)
    return blob.public_url


def is_storage_configured() -> bool:
    return _client is not None and _bucket is not None

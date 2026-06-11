"""Pure HTTP client for posting an application to Greenhouse's public Job
Board API.

Endpoint:
    POST https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}
    Content-Type: multipart/form-data

Field names map 1:1 to the `questions[*].fields[*].name` values returned by
the extractor. Selects send the option `value` (already resolved by the
profile agent's fuzzy match). The `resume` field accepts a file upload.

This module is intentionally framework-free so it can be unit-tested and
re-used from the orchestrator's dry-run path.
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any, Optional

import requests

GREENHOUSE_SUBMIT_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
DEFAULT_TIMEOUT = 30


class SubmitError(Exception):
    """Raised for client-side preparation errors (vs. server-side HTTP errors)."""


def _coerce_value(value: Any) -> Any:
    """Greenhouse expects strings for most fields. Lists are sent as repeated
    keys via the requests library (handled by the caller). Booleans -> 0/1.
    None -> empty string (skipped upstream)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return value


def build_payload(
    filled_fields: list[dict[str, Any]],
    *,
    questions: Optional[list[dict[str, Any]]] = None,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Turn the profile agent's FilledField list into a list of (name, value)
    tuples ready for `requests`' `data=` parameter.

    Returns (text_fields, file_field_names). The caller is responsible for
    opening the resume bytes — we only return which field name(s) expect a
    file so callers can match the resume to the right field.
    """
    # Discover which field names are file uploads from the question schema.
    file_field_names: list[str] = []
    if questions:
        for q in questions:
            for f in q.get("fields") or []:
                if (f.get("type") or "").lower() in {"input_file", "file"}:
                    name = f.get("name")
                    if name:
                        file_field_names.append(name)

    text_fields: list[tuple[str, str]] = []
    for field in filled_fields:
        name = field.get("name")
        value = field.get("value")
        if not name:
            continue
        if name in file_field_names:
            # files are attached separately by the caller
            continue
        if value is None or value == "":
            continue

        if isinstance(value, list):
            for item in value:
                coerced = _coerce_value(item)
                if coerced == "":
                    continue
                text_fields.append((name, str(coerced)))
        else:
            coerced = _coerce_value(value)
            if coerced == "":
                continue
            text_fields.append((name, str(coerced)))

    return text_fields, file_field_names


def check_required(
    questions: list[dict[str, Any]],
    filled_fields: list[dict[str, Any]],
    *,
    have_resume: bool,
) -> list[str]:
    """Return the list of required field names that are NOT satisfied by
    `filled_fields` (or by a resume upload, when the required field IS the
    resume)."""
    filled_names = {
        f["name"]
        for f in filled_fields
        if f.get("name") and f.get("value") not in (None, "", [])
    }
    missing: list[str] = []
    for q in questions or []:
        if not q.get("required"):
            continue
        for f in q.get("fields") or []:
            fname = f.get("name")
            if not fname:
                continue
            ftype = (f.get("type") or "").lower()
            if ftype in {"input_file", "file"}:
                if not have_resume:
                    missing.append(fname)
                continue
            if fname not in filled_names:
                missing.append(fname)
    return missing


def post_application(
    board_token: str,
    job_id: str,
    text_fields: list[tuple[str, str]],
    *,
    resume_path: Optional[str] = None,
    resume_field_name: str = "resume",
    resume_filename: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> requests.Response:
    """POST the multipart form to Greenhouse. Returns the raw `Response`."""
    url = GREENHOUSE_SUBMIT_URL.format(board=board_token, job_id=job_id)

    files: dict[str, tuple[str, bytes, str]] | None = None
    if resume_path:
        path = Path(resume_path)
        if not path.is_file():
            raise SubmitError(f"Resume file does not exist: {resume_path}")
        mime, _ = mimetypes.guess_type(str(path))
        files = {
            resume_field_name: (
                resume_filename or path.name,
                path.read_bytes(),
                mime or "application/octet-stream",
            )
        }

    headers = {
        # Some boards reject obvious bot UAs; mimic a normal client.
        "User-Agent": "fetchai-job-application-agent/0.1 (+https://fetch.ai)",
    }

    return requests.post(
        url,
        data=text_fields,
        files=files,
        headers=headers,
        timeout=timeout,
    )


def parse_response(resp: requests.Response) -> tuple[Optional[str], str]:
    """Pull (application_id, body_text) out of a Greenhouse response.
    application_id is best-effort — the public board API responds with
    different shapes for different boards."""
    body_text = resp.text or ""
    application_id: Optional[str] = None
    try:
        data = resp.json()
        if isinstance(data, dict):
            for key in ("id", "application_id", "applicationId"):
                if key in data and data[key] is not None:
                    application_id = str(data[key])
                    break
            body_text = json.dumps(data)
    except ValueError:
        pass
    return application_id, body_text

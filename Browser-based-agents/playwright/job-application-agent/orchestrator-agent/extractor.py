"""Extracts a structured job posting + application form from a Greenhouse job URL.

Deterministic — no LLM in the loop. Uses Greenhouse's public Job Board API
which returns canonical job content and the application form schema in one call.

Pipeline: parse_url -> fetch_job -> assemble (early-return on any error)
"""

from __future__ import annotations

import html as html_module
import re
from typing import Any, Optional
from urllib.parse import urlparse

import html2text
import requests
from pydantic import BaseModel, Field

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
DEFAULT_TIMEOUT = 20

_URL_PATTERNS = [
    re.compile(r"^/(?P<board>[^/]+)/jobs/(?P<job_id>\d+)"),
    re.compile(r"^/jobs/(?P<job_id>\d+)"),  # vanity host — board from subdomain
]


# ---------------------------------------------------------------------------
# Public output schema
# ---------------------------------------------------------------------------


class JobQuestionField(BaseModel):
    name: str
    type: str = Field(
        description="Greenhouse field type, e.g. input_text, textarea, multi_value_single_select"
    )
    required: bool = False
    label: Optional[str] = None
    values: list[dict[str, Any]] = Field(default_factory=list)


class JobQuestion(BaseModel):
    label: str
    required: bool = False
    description: Optional[str] = None
    fields: list[JobQuestionField] = Field(default_factory=list)


class JobInfo(BaseModel):
    board_token: str
    job_id: str
    title: str
    company: Optional[str] = None
    absolute_url: Optional[str] = None
    location: Optional[str] = None
    departments: list[str] = Field(default_factory=list)
    offices: list[str] = Field(default_factory=list)
    employment_type: Optional[str] = None
    description_markdown: str
    description_html: str
    questions: list[JobQuestion] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    success: bool
    job: Optional[JobInfo] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def _parse_url(url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (board_token, job_id, error)."""
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None, None, f"Not a valid URL: {url!r}"

    host = parsed.netloc.lower()
    if "greenhouse.io" not in host:
        return None, None, f"URL does not look like a Greenhouse job board: {host}"

    board_token: Optional[str] = None
    job_id: Optional[str] = None

    for pattern in _URL_PATTERNS:
        match = pattern.search(parsed.path)
        if not match:
            continue
        groups = match.groupdict()
        job_id = groups["job_id"]
        if "board" in groups:
            board_token = groups["board"]
        break

    if board_token is None and host.endswith(".greenhouse.io"):
        sub = host.split(".greenhouse.io")[0]
        if sub not in {"boards", "job-boards", "boards-api"}:
            board_token = sub.split(".")[-1]

    if not board_token or not job_id:
        return (
            None,
            None,
            (
                "Could not extract board token and job id from URL. "
                "Expected something like https://boards.greenhouse.io/<company>/jobs/<id>"
            ),
        )

    return board_token, job_id, None


def _fetch_job(board: str, job_id: str) -> tuple[Optional[dict], Optional[str]]:
    """Return (raw_json, error)."""
    url = GREENHOUSE_API.format(board=board, job_id=job_id)
    try:
        resp = requests.get(url, params={"questions": "true"}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return None, f"Network error fetching {url}: {exc}"

    if resp.status_code == 404:
        return None, f"Greenhouse returned 404 for board={board!r} job_id={job_id!r}"
    if resp.status_code >= 400:
        return None, f"Greenhouse API error {resp.status_code}: {resp.text[:200]}"

    try:
        return resp.json(), None
    except ValueError as exc:
        return None, f"Invalid JSON from Greenhouse: {exc}"


def _assemble(board_token: str, job_id: str, raw: dict) -> JobInfo:
    html = raw.get("content") or ""
    html_unescaped = html_module.unescape(html)

    converter = html2text.HTML2Text()
    converter.body_width = 0
    converter.ignore_images = True
    markdown = converter.handle(html_unescaped).strip()

    location = (raw.get("location") or {}).get("name")
    departments = [
        d.get("name") for d in (raw.get("departments") or []) if d.get("name")
    ]
    offices = [o.get("name") for o in (raw.get("offices") or []) if o.get("name")]

    employment_type = None
    for m in raw.get("metadata") or []:
        if (m.get("name") or "").lower() in {"employment type", "type"}:
            value = m.get("value")
            employment_type = (
                ", ".join(str(v) for v in value)
                if isinstance(value, list)
                else str(value)
                if value
                else None
            )
            break

    questions: list[JobQuestion] = []
    for q in raw.get("questions") or []:
        fields = [
            JobQuestionField(
                name=f.get("name") or "",
                type=f.get("type") or "unknown",
                required=bool(q.get("required")),
                label=f.get("label"),
                values=f.get("values") or [],
            )
            for f in (q.get("fields") or [])
        ]
        questions.append(
            JobQuestion(
                label=q.get("label") or "",
                required=bool(q.get("required")),
                description=q.get("description"),
                fields=fields,
            )
        )

    return JobInfo(
        board_token=board_token,
        job_id=job_id,
        title=raw.get("title") or "",
        company=raw.get("company_name") or None,
        absolute_url=raw.get("absolute_url"),
        location=location,
        departments=departments,
        offices=offices,
        employment_type=employment_type,
        description_markdown=markdown,
        description_html=html_unescaped,
        questions=questions,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract(url: str) -> ExtractionResult:
    board_token, job_id, err = _parse_url(url)
    if err:
        return ExtractionResult(success=False, error=err)

    raw, err = _fetch_job(board_token, job_id)
    if err:
        return ExtractionResult(success=False, error=err)

    return ExtractionResult(success=True, job=_assemble(board_token, job_id, raw))


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extractor.py <greenhouse_job_url>")
        sys.exit(2)

    out = extract(sys.argv[1])
    print(json.dumps(out.model_dump(), indent=2)[:4000])

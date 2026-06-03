"""LangGraph pipeline that extracts a structured job posting + application form
from a Greenhouse job URL.

The extractor is intentionally deterministic (no LLM in the loop) - it uses
Greenhouse's public Job Board API which returns the canonical job content and
the application form schema in a single call. LangGraph is used to model the
small multi-step pipeline cleanly so it stays composable and easy to extend
(e.g. adding caching, retries, or LLM-based summarization later).

Pipeline:
    parse_url  ->  fetch_job  ->  assemble  ->  END
                      |
                      +--(error)--> END
"""

from __future__ import annotations

import re
from typing import Any, Optional, TypedDict
from urllib.parse import urlparse

import html2text
import requests
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
DEFAULT_TIMEOUT = 20

# Matches Greenhouse job URLs across their public board hosts. The board_token
# is the company slug, and job_id is the numeric posting id.
#   https://boards.greenhouse.io/{board}/jobs/{job_id}
#   https://job-boards.greenhouse.io/{board}/jobs/{job_id}
#   https://{board}.greenhouse.io/jobs/{job_id}     (vanity host)
_URL_PATTERNS = [
    re.compile(r"^/(?P<board>[^/]+)/jobs/(?P<job_id>\d+)"),
    re.compile(r"^/jobs/(?P<job_id>\d+)"),  # vanity host - board comes from subdomain
]


# ---------------------------------------------------------------------------
# Public output schema (also reused by the uAgent wrapper)
# ---------------------------------------------------------------------------


class JobQuestionField(BaseModel):
    name: str
    type: str = Field(description="Greenhouse field type, e.g. input_text, textarea, multi_value_single_select")
    required: bool = False
    label: Optional[str] = None
    values: list[dict[str, Any]] = Field(
        default_factory=list,
        description="For select-type fields: the allowed options (label/value pairs).",
    )


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
# Graph state
# ---------------------------------------------------------------------------


class _State(TypedDict, total=False):
    url: str
    board_token: str
    job_id: str
    raw: dict[str, Any]
    result: ExtractionResult
    error: str


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _parse_url(state: _State) -> _State:
    url = state["url"].strip()
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return {"error": f"Not a valid URL: {url!r}"}

    host = parsed.netloc.lower()
    if "greenhouse.io" not in host:
        return {"error": f"URL does not look like a Greenhouse job board: {host}"}

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

    # Vanity host: company.greenhouse.io/jobs/123 -> board_token from subdomain.
    if board_token is None and host.endswith(".greenhouse.io"):
        sub = host.split(".greenhouse.io")[0]
        # Exclude the standard hosts.
        if sub not in {"boards", "job-boards", "boards-api"}:
            board_token = sub.split(".")[-1]

    if not board_token or not job_id:
        return {
            "error": (
                "Could not extract board token and job id from URL. "
                "Expected something like https://boards.greenhouse.io/<company>/jobs/<id>"
            )
        }

    return {"board_token": board_token, "job_id": job_id}


def _fetch_job(state: _State) -> _State:
    board = state["board_token"]
    job_id = state["job_id"]
    url = GREENHOUSE_API.format(board=board, job_id=job_id)
    try:
        resp = requests.get(url, params={"questions": "true"}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return {"error": f"Network error fetching {url}: {exc}"}

    if resp.status_code == 404:
        return {"error": f"Greenhouse returned 404 for board={board!r} job_id={job_id!r}"}
    if resp.status_code >= 400:
        return {"error": f"Greenhouse API error {resp.status_code}: {resp.text[:200]}"}

    try:
        return {"raw": resp.json()}
    except ValueError as exc:
        return {"error": f"Invalid JSON from Greenhouse: {exc}"}


def _assemble(state: _State) -> _State:
    raw = state["raw"]

    html = raw.get("content") or ""
    # Greenhouse returns HTML-escaped content; unescape entities then convert to markdown.
    import html as html_module

    html_unescaped = html_module.unescape(html)

    converter = html2text.HTML2Text()
    converter.body_width = 0  # don't hard-wrap
    converter.ignore_images = True
    markdown = converter.handle(html_unescaped).strip()

    location = (raw.get("location") or {}).get("name")
    departments = [d.get("name") for d in (raw.get("departments") or []) if d.get("name")]
    offices = [o.get("name") for o in (raw.get("offices") or []) if o.get("name")]

    questions: list[JobQuestion] = []
    for q in raw.get("questions") or []:
        fields = []
        for f in q.get("fields") or []:
            fields.append(
                JobQuestionField(
                    name=f.get("name") or "",
                    type=f.get("type") or "unknown",
                    required=bool(q.get("required")),
                    label=f.get("label"),
                    values=f.get("values") or [],
                )
            )
        questions.append(
            JobQuestion(
                label=q.get("label") or "",
                required=bool(q.get("required")),
                description=q.get("description"),
                fields=fields,
            )
        )

    company = (raw.get("company_name")) or None
    metadata = raw.get("metadata") or []
    employment_type = None
    for m in metadata:
        if (m.get("name") or "").lower() in {"employment type", "type"}:
            value = m.get("value")
            if isinstance(value, list):
                employment_type = ", ".join(str(v) for v in value)
            elif value is not None:
                employment_type = str(value)
            break

    job = JobInfo(
        board_token=state["board_token"],
        job_id=state["job_id"],
        title=raw.get("title") or "",
        company=company,
        absolute_url=raw.get("absolute_url"),
        location=location,
        departments=departments,
        offices=offices,
        employment_type=employment_type,
        description_markdown=markdown,
        description_html=html_unescaped,
        questions=questions,
    )
    return {"result": ExtractionResult(success=True, job=job)}


def _on_error(state: _State) -> _State:
    return {"result": ExtractionResult(success=False, error=state.get("error", "Unknown error"))}


def _has_error(state: _State) -> str:
    return "error" if state.get("error") else "ok"


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_graph():
    graph = StateGraph(_State)
    graph.add_node("parse_url", _parse_url)
    graph.add_node("fetch_job", _fetch_job)
    graph.add_node("assemble", _assemble)
    graph.add_node("on_error", _on_error)

    graph.set_entry_point("parse_url")
    graph.add_conditional_edges("parse_url", _has_error, {"ok": "fetch_job", "error": "on_error"})
    graph.add_conditional_edges("fetch_job", _has_error, {"ok": "assemble", "error": "on_error"})
    graph.add_edge("assemble", END)
    graph.add_edge("on_error", END)

    return graph.compile()


_compiled = None


def extract(url: str) -> ExtractionResult:
    """Run the LangGraph pipeline on a Greenhouse job URL and return a typed result."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    final = _compiled.invoke({"url": url})
    result = final.get("result")
    if result is None:
        return ExtractionResult(success=False, error="Pipeline produced no result")
    return result


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extractor.py <greenhouse_job_url>")
        sys.exit(2)

    out = extract(sys.argv[1])
    print(json.dumps(out.model_dump(), indent=2)[:4000])

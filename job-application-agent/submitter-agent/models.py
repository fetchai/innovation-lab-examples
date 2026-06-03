"""Shared pydantic models for the submitter agent.

Canonical pydantic v2 shapes used internally. On the uAgents wire we keep
JSON-as-string for the rich payloads (`job_json`, `filled_json`) because
uagents builds its message schema with pydantic v1 internals and cannot
introspect nested v2 models — same pattern as the extractor / profile agents.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SubmissionAttempt(BaseModel):
    """Structured record of a single submission attempt."""

    board_token: str
    job_id: str
    dry_run: bool
    fields_submitted: list[str] = Field(default_factory=list)
    resume_filename: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    application_id: Optional[str] = None
    error: Optional[str] = None
    success: bool = False


class PreparedPayload(BaseModel):
    """The multipart payload the agent is about to post, captured for logging
    or for `dry_run` inspection."""

    url: str
    text_fields: dict[str, Any] = Field(default_factory=dict)
    file_field: Optional[str] = None  # name of the file field, e.g. "resume"
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None

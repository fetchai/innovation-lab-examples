"""Shared pydantic models for the profile agent.

These are the *canonical* (pydantic v2) shapes used inside the agent and by
any importing helper. On the uAgents wire we use JSON-encoded strings because
uagents builds its message schema with pydantic v1 internals and can't
introspect nested v2 models / Any (same reason as in the extractor agent).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

DEFAULT_USER_KEY = "me"


class EducationEntry(BaseModel):
    university_name: Optional[str] = None
    degree: Optional[str] = None
    major: Optional[str] = None
    graduation_date: Optional[str] = None
    gpa: Optional[str] = None
    gpa_scale: Optional[str] = None  # "4.0", "4.3", "5.0", "7.0", "10.0", "percentage", "pass_fail"
    degree_level: Optional[str] = None  # "high_school", "associate", "bachelor", "master", "doctoral", "certificate"


class ExperienceEntry(BaseModel):
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    employment_type: Optional[str] = None  # "full_time", "part_time", "internship", "contract", "freelance", "volunteer"
    location: Optional[str] = None
    work_mode: Optional[str] = None  # "onsite", "remote", "hybrid"
    start_date: Optional[str] = None
    end_date: Optional[str] = None  # None / blank = currently working
    description: Optional[str] = None


class UserProfile(BaseModel):
    """Canonical user profile. All fields except first/last/email are optional."""

    # Identity / contact
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    preferred_name: Optional[str] = None
    email: str
    phone: Optional[str] = None

    # Location
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip_code: Optional[str] = None

    # Links
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    twitter: Optional[str] = None

    # Work authorization
    work_authorization: Optional[str] = Field(
        default=None,
        description="e.g. 'US Citizen', 'Permanent Resident', 'Student Visa - F1', 'H1B'",
    )
    needs_sponsorship: Optional[bool] = None
    requires_visa: Optional[bool] = None

    # EEO / voluntary disclosures (all optional)
    gender: Optional[str] = None
    race_ethnicity: Optional[str] = None
    veteran_status: Optional[str] = None
    disability_status: Optional[str] = None

    # Resume
    resume_path: Optional[str] = Field(default=None, description="Absolute path to the resume file on disk")
    resume_text: Optional[str] = Field(default=None, description="Plain-text extraction of the resume")

    # Reusable free-text answers keyed by normalized question label.
    canned_answers: dict[str, str] = Field(default_factory=dict)

    # Education history
    education: list[EducationEntry] = Field(default_factory=list)

    # Work experience
    experience: list[ExperienceEntry] = Field(default_factory=list)

    # Extra fields the user wants to remember but doesn't fit a column.
    extras: dict[str, Any] = Field(default_factory=dict)

    updated_at: Optional[str] = None

    def touch(self) -> "UserProfile":
        self.updated_at = datetime.now(UTC).isoformat()
        return self


class FilledField(BaseModel):
    """One filled application form field."""

    name: str
    value: Any
    source: str = Field(description="Where the value came from: 'profile', 'canned', 'rag', 'llm', 'file'")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    question_label: Optional[str] = None


class MapFieldsResult(BaseModel):
    """Result of mapping a Greenhouse question list against a stored profile."""

    success: bool
    filled: list[FilledField] = Field(default_factory=list)
    missing: list[str] = Field(
        default_factory=list,
        description="Names of fields the agent could not fill confidently.",
    )
    error: Optional[str] = None

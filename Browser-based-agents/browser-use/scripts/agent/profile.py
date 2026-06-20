"""
User profile for hackathon registration.

Load from ~/.hackathon_profile.json or a custom path.
The profile is used to:
  1. Auto-fill standard fields (name, email, LinkedIn, GitHub)
  2. Generate custom answers to open-ended questions via ASI:One

Usage:
    from agent.profile import UserProfile, load_profile, save_profile

    profile = load_profile()          # loads from ~/.hackathon_profile.json
    profile = UserProfile(            # or create inline
        first_name="Aditya",
        last_name="...",
        email="...",
        ...
    )
    save_profile(profile)
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEFAULT_PROFILE_PATH = Path.home() / ".hackathon_profile.json"


@dataclass
class UserProfile:
    # Identity
    first_name: str = ""
    last_name: str = ""
    email: str = ""

    # Social / professional links
    linkedin_url: str = ""
    github_url: str = ""
    twitter_handle: str = ""
    personal_site: str = ""

    # Location
    city: str = ""
    country: str = ""

    # Background
    bio: str = ""                  # 2-3 sentence intro about yourself
    skills: list[str] = field(default_factory=list)   # e.g. ["Python", "LLMs", "React"]
    experience_level: str = ""     # "student" | "junior" | "mid" | "senior"
    role: str = ""                 # e.g. "Full-stack Engineer", "ML Researcher"
    company_or_school: str = ""

    # Common hackathon Q&A
    proud_project: str = ""        # "What AI project are you most proud of?"
    what_to_build: str = ""        # "What do you want to build?" — overridden per event
    why_this_event: str = ""       # "Why do you want to attend?" — overridden per event
    looking_for_job: bool = False
    team_members: str = ""         # "Name (email), Name (email)" or empty for solo
    needs_visa: bool = False

    # Auth credentials (used for platform logins — stored locally only, never in DB)
    cerebralvalley_email: str = ""
    cerebralvalley_password: str = ""
    luma_email: str = ""           # Luma uses magic link, so just email is enough
    devpost_email: str = ""
    devpost_password: str = ""

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def location_str(self) -> str:
        parts = [p for p in [self.city, self.country] if p]
        return ", ".join(parts)

    def github_username(self) -> str:
        return self.github_url.rstrip("/").split("/")[-1] if self.github_url else ""

    def twitter_url(self) -> str:
        if not self.twitter_handle:
            return ""
        handle = self.twitter_handle.lstrip("@")
        return f"https://x.com/{handle}"


def load_profile(path: str | Path | None = None) -> UserProfile:
    """Load profile from JSON file. Returns empty profile if file doesn't exist."""
    fpath = Path(path) if path else DEFAULT_PROFILE_PATH
    if not fpath.exists():
        print(f"  [PROFILE] No profile found at {fpath}. Using empty profile.")
        print(f"  [PROFILE] Run save_profile() to create one.")
        return UserProfile()
    with open(fpath) as f:
        data = json.load(f)
    return UserProfile(**{k: v for k, v in data.items() if k in UserProfile.__dataclass_fields__})


def save_profile(profile: UserProfile, path: str | Path | None = None) -> None:
    """Save profile to JSON file."""
    fpath = Path(path) if path else DEFAULT_PROFILE_PATH
    with open(fpath, "w") as f:
        json.dump(asdict(profile), f, indent=2)
    print(f"  [PROFILE] Saved to {fpath}")


def profile_to_context(profile: UserProfile) -> str:
    """Render profile as a readable context string for LLM prompts."""
    lines = [
        f"Name: {profile.full_name()}",
        f"Email: {profile.email}",
        f"Role: {profile.role or 'Software Engineer'}",
        f"Experience: {profile.experience_level}",
        f"Company/School: {profile.company_or_school}",
        f"Location: {profile.location_str()}",
        f"Skills: {', '.join(profile.skills)}",
        f"LinkedIn: {profile.linkedin_url}",
        f"GitHub: {profile.github_url}",
        f"Twitter: {profile.twitter_handle}",
        f"Bio: {profile.bio}",
        f"Proud project: {profile.proud_project}",
        f"Looking for job: {'yes' if profile.looking_for_job else 'no'}",
        f"Team members: {profile.team_members or 'solo'}",
    ]
    return "\n".join(l for l in lines if not l.endswith(": "))

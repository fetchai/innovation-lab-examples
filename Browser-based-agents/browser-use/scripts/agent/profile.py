"""
User profile for hackathon registration.

Production storage is Supabase (table `hackathon_profiles`), keyed by
`agent_address` — the uAgents sender address of whoever is chatting with the
deployed bot (see agent.py's `_sess(sender)`). That address is already
authenticated by the uAgents messaging layer, so it doubles as a per-user id
without a separate login step, and keeps one user's profile from ever being
read or overwritten by another user's chat session.

A local JSON file (~/.hackathon_profile.json or a custom path) is still
supported for solo CLI usage (create_profile.py, register.py --profile) where
there's no chat sender to key off of. Pass `agent_address` to use Supabase
instead; pass `path`/nothing to use the local file. The two are independent
stores — profiles are not auto-synced between them.

Usage:
    from agent.profile import UserProfile, load_profile, save_profile

    profile = load_profile()                     # local file (CLI/dev use)
    profile = load_profile(agent_address=sender)  # Supabase (production, per-user)

    profile = UserProfile(            # or create inline
        first_name="Aditya",
        last_name="...",
        email="...",
        ...
    )
    save_profile(profile, agent_address=sender)
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEFAULT_PROFILE_PATH = Path.home() / ".hackathon_profile.json"

_PROFILES_TABLE = "hackathon_profiles"


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

    # Merch / logistics
    tshirt_size: str = ""          # e.g. "M", "L" — commonly asked, rarely worth an LLM guess

    # Answers learned on the fly from the human when a registration form asks
    # something the profile has no field for (e.g. "dietary restrictions",
    # "allergies", "pronouns"). Keyed by a short normalized field name.
    custom_fields: dict[str, str] = field(default_factory=dict)

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


def load_profile(path: str | Path | None = None, agent_address: str | None = None) -> UserProfile:
    """
    Load a profile. If `agent_address` is given, loads that user's row from
    Supabase (returns an empty profile if they have none yet). Otherwise
    loads from the local JSON file, returning an empty profile if it doesn't
    exist.
    """
    if agent_address:
        return _load_profile_remote(agent_address)

    fpath = Path(path) if path else DEFAULT_PROFILE_PATH
    if not fpath.exists():
        print(f"  [PROFILE] No profile found at {fpath}. Using empty profile.")
        print(f"  [PROFILE] Run save_profile() to create one.")
        return UserProfile()
    with open(fpath) as f:
        data = json.load(f)
    return UserProfile(**{k: v for k, v in data.items() if k in UserProfile.__dataclass_fields__})


def save_profile(profile: UserProfile, path: str | Path | None = None, agent_address: str | None = None) -> None:
    """Save a profile. If `agent_address` is given, upserts to Supabase (keyed
    by that address) instead of writing the local JSON file."""
    if agent_address:
        _save_profile_remote(agent_address, profile)
        return

    fpath = Path(path) if path else DEFAULT_PROFILE_PATH
    with open(fpath, "w") as f:
        json.dump(asdict(profile), f, indent=2)
    print(f"  [PROFILE] Saved to {fpath}")


def _load_profile_remote(agent_address: str) -> UserProfile:
    """Load a user's profile from the `hackathon_profiles` Supabase table."""
    from db import get_service_client  # local import: keeps pure-local/CLI usage from requiring Supabase config

    try:
        client = get_service_client()
        rows = (
            client.table(_PROFILES_TABLE)
            .select("*")
            .eq("agent_address", agent_address)
            .limit(1)
            .execute()
            .data
        )
    except Exception as e:
        print(f"  [PROFILE] Supabase load failed for {agent_address[:12]}...: {e}")
        return UserProfile()

    if not rows:
        return UserProfile()

    data = rows[0]
    return UserProfile(**{k: v for k, v in data.items() if k in UserProfile.__dataclass_fields__})


def _save_profile_remote(agent_address: str, profile: UserProfile) -> None:
    """Upsert a user's profile into the `hackathon_profiles` Supabase table."""
    from db import get_service_client  # local import: keeps pure-local/CLI usage from requiring Supabase config

    row = asdict(profile)
    row["agent_address"] = agent_address
    try:
        client = get_service_client()
        client.table(_PROFILES_TABLE).upsert(row, on_conflict="agent_address").execute()
        print(f"  [PROFILE] Saved to Supabase for {agent_address[:12]}...")
    except Exception as e:
        print(f"  [PROFILE] Supabase save failed for {agent_address[:12]}...: {e}")


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
        f"T-shirt size: {profile.tshirt_size}",
    ]
    if profile.custom_fields:
        lines.append("Previously learned answers: " + ", ".join(
            f"{k}={v}" for k, v in profile.custom_fields.items() if v
        ))
    return "\n".join(l for l in lines if not l.endswith(": "))

"""
User profile for hackathon registration.

Supabase (table `hackathon_profiles`) is the SOLE source of truth for profile
data. Production/chat usage keys rows by `agent_address` — the uAgents sender
address of whoever is chatting with the deployed bot (see agent.py's
`_sess(sender)`); that address is already authenticated by the uAgents
messaging layer, so it doubles as a per-user id without a separate login
step. Solo CLI usage (create_profile.py, register.py) with no `agent_address`
now ALSO reads/writes Supabase, under the fixed key `LOCAL_AGENT_ADDRESS`
(env-overridable) — there is no independent local-only profile store anymore,
so CLI runs and the chat bot can never see divergent data for the same
logical row.

A local JSON file is only ever used if you explicitly pass `path` — an
offline/import escape hatch, not a parallel source of truth. It is never read
or written implicitly.

Usage:
    from agent.profile import UserProfile, load_profile, save_profile

    profile = load_profile()                     # Supabase, key=LOCAL_AGENT_ADDRESS (CLI/dev use)
    profile = load_profile(agent_address=sender)  # Supabase (production, per-user)
    profile = load_profile(path="/tmp/x.json")    # explicit local file — offline use only

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

# Fixed Supabase row key used by solo CLI usage (no chat sender to key off
# of). Override via env if you want a different personal key than the shared
# default — but note it's still a DB row, not a local file.
LOCAL_AGENT_ADDRESS = os.environ.get("LOCAL_AGENT_ADDRESS", "local-cli-default")

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
    bio: str = ""  # 2-3 sentence intro about yourself
    skills: list[str] = field(default_factory=list)  # e.g. ["Python", "LLMs", "React"]
    experience_level: str = ""  # "student" | "junior" | "mid" | "senior"
    role: str = ""  # e.g. "Full-stack Engineer", "ML Researcher"
    company_or_school: str = ""

    # Common hackathon Q&A
    proud_project: str = ""  # "What AI project are you most proud of?"
    what_to_build: str = ""  # "What do you want to build?" — overridden per event
    why_this_event: str = ""  # "Why do you want to attend?" — overridden per event
    # None = never asked/unknown — must NOT be treated as False. See answer_gen.py,
    # which only auto-answers these from the profile when they're actually set,
    # and otherwise routes the question to the human instead of guessing "no".
    looking_for_job: bool | None = None
    team_members: str = ""  # "Name (email), Name (email)" or empty for solo
    needs_visa: bool | None = None

    # Auth credentials (used for platform logins — stored locally only, never in DB)
    cerebralvalley_email: str = ""
    cerebralvalley_password: str = ""
    luma_email: str = ""  # Luma uses magic link, so just email is enough
    devpost_email: str = ""
    devpost_password: str = ""

    # Merch / logistics
    tshirt_size: str = ""  # e.g. "M", "L" — commonly asked, rarely worth an LLM guess

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


def load_profile(
    path: str | Path | None = None, agent_address: str | None = None
) -> UserProfile:
    """
    Load a profile from Supabase — the single source of truth. Reads the row
    keyed by `agent_address` if given, else the fixed `LOCAL_AGENT_ADDRESS`
    key used by solo CLI usage. Returns an empty profile if that row doesn't
    exist yet.

    Only reads the local JSON file if `path` is explicitly passed — an
    offline/import escape hatch, never the implicit default.
    """
    if path:
        fpath = Path(path)
        if not fpath.exists():
            print(f"  [PROFILE] No profile found at {fpath}. Using empty profile.")
            return UserProfile()
        with open(fpath) as f:
            data = json.load(f)
        return UserProfile(
            **{k: v for k, v in data.items() if k in UserProfile.__dataclass_fields__}
        )

    return _load_profile_remote(agent_address or LOCAL_AGENT_ADDRESS)


def save_profile(
    profile: UserProfile,
    path: str | Path | None = None,
    agent_address: str | None = None,
) -> None:
    """Save a profile to Supabase — the single source of truth. Upserts the
    row keyed by `agent_address` if given, else the fixed `LOCAL_AGENT_ADDRESS`
    key used by solo CLI usage.

    Only writes the local JSON file if `path` is explicitly passed — an
    offline/import escape hatch, never the implicit default.
    """
    if path:
        fpath = Path(path)
        with open(fpath, "w") as f:
            json.dump(asdict(profile), f, indent=2)
        print(f"  [PROFILE] Saved to {fpath}")
        return

    _save_profile_remote(agent_address or LOCAL_AGENT_ADDRESS, profile)


def _load_profile_remote(agent_address: str) -> UserProfile:
    """Load a user's profile from the `hackathon_profiles` Supabase table."""
    from db import (
        get_service_client,
    )  # local import: keeps pure-local/CLI usage from requiring Supabase config

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
    return UserProfile(
        **{k: v for k, v in data.items() if k in UserProfile.__dataclass_fields__}
    )


def _save_profile_remote(agent_address: str, profile: UserProfile) -> None:
    """Upsert a user's profile into the `hackathon_profiles` Supabase table."""
    from db import (
        get_service_client,
    )  # local import: keeps pure-local/CLI usage from requiring Supabase config

    row = asdict(profile)
    row["agent_address"] = agent_address
    try:
        client = get_service_client()
        client.table(_PROFILES_TABLE).upsert(row, on_conflict="agent_address").execute()
        print(f"  [PROFILE] Saved to Supabase for {agent_address[:12]}...")
    except Exception as e:
        print(f"  [PROFILE] Supabase save failed for {agent_address[:12]}...: {e}")


def _tri_state(val: bool | None) -> str:
    return "unknown" if val is None else ("yes" if val else "no")


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
        f"Looking for job: {_tri_state(profile.looking_for_job)}",
        f"Team members: {profile.team_members or 'solo'}",
        f"Needs visa sponsorship: {_tri_state(profile.needs_visa)}",
        f"T-shirt size: {profile.tshirt_size}",
    ]
    if profile.custom_fields:
        lines.append(
            "Previously learned answers: "
            + ", ".join(f"{k}={v}" for k, v in profile.custom_fields.items() if v)
        )
    return "\n".join(line for line in lines if not line.endswith(": "))

"""
Interactive CLI to create/update your hackathon registration profile.
Run once: python scripts/agent/create_profile.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.profile import UserProfile, save_profile, DEFAULT_PROFILE_PATH

def prompt(label, default=""):
    val = input(f"{label}{f' [{default}]' if default else ''}: ").strip()
    return val if val else default

print("\n=== Hackathon Registration Profile Setup ===\n")
print(f"This will save to {DEFAULT_PROFILE_PATH}\n")

p = UserProfile(
    first_name     = prompt("First name"),
    last_name      = prompt("Last name"),
    email          = prompt("Email"),
    linkedin_url   = prompt("LinkedIn URL"),
    github_url     = prompt("GitHub URL"),
    twitter_handle = prompt("Twitter/X handle (without @)"),
    city           = prompt("City"),
    country        = prompt("Country"),
    role           = prompt("Your role (e.g. ML Engineer, Full-stack Dev)"),
    experience_level = prompt("Experience level (student/junior/mid/senior)"),
    company_or_school = prompt("Company or school"),
    bio            = prompt("Short bio (2-3 sentences about yourself)"),
    proud_project  = prompt("Proudest AI project (1 sentence)"),
    looking_for_job = prompt("Looking for a job? (yes/no)", "no").lower() == "yes",
    skills         = [s.strip() for s in prompt("Top skills (comma-separated)").split(",") if s.strip()],
    # Auth
    cerebralvalley_email    = prompt("Cerebral Valley email (for registration login, optional)"),
    cerebralvalley_password = prompt("Cerebral Valley password (optional)"),
    luma_email     = prompt("Luma email for RSVP (optional, defaults to main email)"),
    devpost_email  = prompt("Devpost email (optional)"),
    devpost_password = prompt("Devpost password (optional)"),
)

save_profile(p)
print(f"\n✅ Profile saved to {DEFAULT_PROFILE_PATH}")
print("\nYou can now register for events with:")
print("  python scripts/agent/register.py --event aiewf-hackathon-2026 --dry-run")

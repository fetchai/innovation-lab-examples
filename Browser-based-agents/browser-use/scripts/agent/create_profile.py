"""
Interactive CLI to create/update your hackathon registration profile.
Run once: python scripts/agent/create_profile.py

Saves to Supabase — the single source of truth for profiles — under the
fixed key agent.profile.LOCAL_AGENT_ADDRESS by default. Pass --agent-address
<address> to instead save under that uAgents address (e.g. to test the
production chat-bot storage path for a specific user without going through
the bot itself).
"""

import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.profile import UserProfile, save_profile, LOCAL_AGENT_ADDRESS

parser = argparse.ArgumentParser()
parser.add_argument("--agent-address", help="Save to Supabase under this agent address instead of the default local CLI key")
args = parser.parse_args()

def prompt(label, default=""):
    val = input(f"{label}{f' [{default}]' if default else ''}: ").strip()
    return val if val else default

def prompt_tribool(label):
    """Returns True/False if answered, or None if left blank — never guess."""
    val = input(f"{label} (yes/no, leave blank if unsure): ").strip().lower()
    if not val:
        return None
    return val == "yes"

print("\n=== Hackathon Registration Profile Setup ===\n")
print(f"This will save to Supabase (agent_address={args.agent_address or LOCAL_AGENT_ADDRESS})\n")

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
    looking_for_job = prompt_tribool("Looking for a job?"),
    needs_visa     = prompt_tribool("Do you need visa sponsorship?"),
    skills         = [s.strip() for s in prompt("Top skills (comma-separated)").split(",") if s.strip()],
    # Auth
    cerebralvalley_email    = prompt("Cerebral Valley email (for registration login, optional)"),
    cerebralvalley_password = prompt("Cerebral Valley password (optional)"),
    luma_email     = prompt("Luma email for RSVP (optional, defaults to main email)"),
    devpost_email  = prompt("Devpost email (optional)"),
    devpost_password = prompt("Devpost password (optional)"),
)

save_profile(p, agent_address=args.agent_address)
print(f"\n✅ Profile saved to Supabase (agent_address={args.agent_address or LOCAL_AGENT_ADDRESS})")
print("\nYou can now register for events with:")
print("  python scripts/agent/register.py --event aiewf-hackathon-2026 --dry-run")

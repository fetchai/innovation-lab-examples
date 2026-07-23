-- Hackathon registration profiles, migrated off the local
-- ~/.hackathon_profile.json file so the Hackrawl agent can serve many
-- concurrent chat users without one user's data leaking into another's.
--
-- Row identity: `agent_address` is the uAgents sender address of whoever is
-- chatting with the deployed agent (see agent.py's `_sess(sender)` / the
-- chat protocol's cryptographically-signed `sender` field). It is the
-- equivalent of a user id for this deployment and is already authenticated
-- by the uAgents messaging layer itself, so no separate Supabase Auth login
-- is required for the bot to know who it's talking to.
--
-- Access model: RLS is enabled with NO policies for `anon` / `authenticated`,
-- so this table is readable/writable only via the `service_role` key. That
-- key must stay server-side only (agent.py, register.py, create_profile.py)
-- and must never be shipped to a browser or mobile client. When the web
-- frontend + onboarding flow is built, add explicit policies scoped to
-- `auth.uid()` for whatever end-user auth method it uses, rather than
-- relaxing this table to `anon`.

create table if not exists hackathon_profiles (
  agent_address text primary key,

  -- Identity
  first_name text not null default '',
  last_name  text not null default '',
  email      text not null default '',

  -- Social / professional links
  linkedin_url   text not null default '',
  github_url     text not null default '',
  twitter_handle text not null default '',
  personal_site  text not null default '',

  -- Location
  city    text not null default '',
  country text not null default '',

  -- Background
  bio               text not null default '',
  skills            jsonb not null default '[]',
  experience_level  text not null default '',
  role              text not null default '',
  company_or_school text not null default '',

  -- Common hackathon Q&A
  proud_project   text not null default '',
  what_to_build   text not null default '',
  why_this_event  text not null default '',
  looking_for_job boolean not null default false,
  team_members    text not null default '',
  needs_visa      boolean not null default false,

  -- Platform login credentials
  -- NOTE: stored in plaintext, matching the previous local-JSON behavior.
  -- Follow-up hardening (not done here): move these into Supabase Vault
  -- (pgsodium) or a separate encrypted-at-rest secrets table.
  cerebralvalley_email    text not null default '',
  cerebralvalley_password text not null default '',
  luma_email              text not null default '',
  devpost_email           text not null default '',
  devpost_password        text not null default '',

  -- Merch / logistics
  tshirt_size text not null default '',

  -- Answers learned on the fly for questions the profile has no field for
  custom_fields jsonb not null default '{}',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table hackathon_profiles enable row level security;
-- Intentionally no policies: default-deny for anon/authenticated, full
-- access for service_role (which bypasses RLS). See access model note above.

create or replace function hackathon_profiles_set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql
set search_path = '';

drop trigger if exists trg_hackathon_profiles_updated_at on hackathon_profiles;
create trigger trg_hackathon_profiles_updated_at
  before update on hackathon_profiles
  for each row
  execute function hackathon_profiles_set_updated_at();

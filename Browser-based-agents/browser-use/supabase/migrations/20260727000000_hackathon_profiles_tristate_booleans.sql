-- looking_for_job/needs_visa previously defaulted to `false`, which was
-- indistinguishable from a user who was actually asked and said no. That let
-- registration forms get a confident "no" answer for people who were never
-- asked at all (see scripts/agent/answer_gen.py). Both columns become
-- nullable with no default, so NULL means "unknown — ask the human" and only
-- an explicit true/false is ever treated as a real answer.
--
-- NOTE: existing rows already storing `false` are NOT backfilled to NULL
-- here, since we can't distinguish a genuine "no" from an unasked default in
-- already-saved data — that ambiguity predates this migration and isn't
-- something we can resolve retroactively.

alter table hackathon_profiles
  alter column looking_for_job drop default,
  alter column looking_for_job drop not null,
  alter column needs_visa drop default,
  alter column needs_visa drop not null;

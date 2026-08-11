"""
Generate answers to hackathon registration questions using ASI:One.

Takes the event's stored `questions` list + the user's profile and
returns a dict mapping question text → answer string.

This runs BEFORE browser-use opens the browser, so the agent has
pre-generated answers ready to paste — no LLM calls needed mid-form.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from agent.profile import UserProfile, profile_to_context
from config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL, ASI_ONE_MODEL

# Preset question types we can answer directly from profile fields
PRESET_MAP = {
    "linkedin": lambda p: p.linkedin_url,
    "github": lambda p: p.github_url,
    "twitter": lambda p: p.twitter_url(),
    "email": lambda p: p.email,
    "name": lambda p: p.full_name(),
    "firstname": lambda p: p.first_name,
    "lastname": lambda p: p.last_name,
}


def generate_answers(
    questions: list[dict],
    profile: UserProfile,
    event_title: str = "",
    event_description: str = "",
) -> dict[str, str]:
    """
    Generate answers for all registration questions.

    Returns dict: {question_text: answer_string}
    """
    if not questions:
        return {}

    answers: dict[str, str] = {}
    open_ended: list[dict] = []

    # Pass 1: answer preset/simple questions directly from profile
    for q in questions:
        question_text = q.get("question", "")
        preset = q.get("preset", "")

        if preset and preset in PRESET_MAP:
            answers[question_text] = PRESET_MAP[preset](profile)
            continue

        # Heuristic direct matches
        q_lower = question_text.lower()
        if "linkedin" in q_lower:
            answers[question_text] = profile.linkedin_url
        elif "github" in q_lower:
            answers[question_text] = profile.github_url
        elif "twitter" in q_lower or "x.com" in q_lower or "x?" in q_lower:
            answers[question_text] = profile.twitter_url() or profile.twitter_handle
        elif "email" in q_lower:
            answers[question_text] = profile.email
        elif "your name" in q_lower or q_lower == "name":
            answers[question_text] = profile.full_name()
        elif "first name" in q_lower:
            answers[question_text] = profile.first_name
        elif "last name" in q_lower:
            answers[question_text] = profile.last_name
        elif "location" in q_lower or "where are you" in q_lower:
            answers[question_text] = profile.location_str()
        elif "looking for a job" in q_lower or "seeking" in q_lower:
            # None = never asked — leave unanswered rather than defaulting to "no"; the
            # NEVER GUESS rule in platforms/generic.py's task prompt then makes the
            # browser agent stop and ask the human instead of picking a default.
            if profile.looking_for_job is not None:
                answers[question_text] = "yes" if profile.looking_for_job else "no"
        elif "visa" in q_lower:
            if profile.needs_visa is not None:
                answers[question_text] = "yes" if profile.needs_visa else "no"
        elif "team" in q_lower and "member" in q_lower:
            answers[question_text] = profile.team_members or "Solo"
        elif "proud" in q_lower and profile.proud_project:
            answers[question_text] = profile.proud_project
        else:
            open_ended.append(q)

    # Pass 2: LLM generates answers for open-ended questions
    if open_ended:
        llm_answers = _llm_generate(open_ended, profile, event_title, event_description)
        answers.update(llm_answers)

    return answers


def _llm_generate(
    questions: list[dict],
    profile: UserProfile,
    event_title: str,
    event_description: str,
) -> dict[str, str]:
    """Use ASI:One to answer open-ended questions."""
    q_list = "\n".join(
        f"{i + 1}. {q['question']}{' (required)' if q.get('required') else ' (optional)'}"
        for i, q in enumerate(questions)
    )

    prompt = f"""You are helping {profile.full_name()} register for a hackathon.

User profile:
{profile_to_context(profile)}

Event: {event_title}
{f"About: {event_description[:500]}" if event_description else ""}

Answer the following registration questions on behalf of this user.
Be authentic, specific, and concise (1-3 sentences per answer).
Use first person ("I"). Match the answer to the user's background and the event theme.

Questions:
{q_list}

Return ONLY a JSON object mapping question number to answer:
{{"1": "answer...", "2": "answer...", ...}}"""

    try:
        resp = httpx.post(
            f"{ASI_ONE_BASE_URL}/chat/completions",
            json={
                "model": ASI_ONE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.7,
            },
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*", "", content).rstrip("```").strip()
        numbered = json.loads(content)

        result = {}
        for i, q in enumerate(questions):
            answer = numbered.get(str(i + 1), "")
            if answer:
                result[q["question"]] = answer
        return result
    except Exception as e:
        print(f"  [ANSWERS] LLM generation failed: {e}")
        return {}


def classify_and_generate_field_answers(
    missing_fields: list[dict],
    profile: UserProfile,
    event_title: str = "",
    event_description: str = "",
) -> dict[str, str]:
    """
    For fields platforms/generic.py's DO NOT GUESS protocol left unanswered
    (no match anywhere in the profile), decide which are safe for the AI to
    answer on the user's behalf vs which must be asked of the human, and
    generate answers for the safe ones — so the human is only ever nudged
    for things that are genuinely about them, not for every single unknown
    field indiscriminately.

    Safe to auto-answer ("opinion"): open-ended, forward-looking questions
    about what the person wants to explore/build/try/discuss AT THIS EVENT
    (e.g. "what would you build/break/prove?", "which topic interests you
    most?"). These aren't facts about the person — they're a
    personalized-sounding answer generated from role/skills/bio, exactly
    like the LLM generation generate_answers() already does above for
    open-ended questions that were pre-crawled ahead of time. Generating
    one here is not a "guess" in the sense the DO NOT GUESS rule forbids;
    it's the same kind of authentic-voice answer, just discovered live.

    NOT safe ("personal_fact", always left for the human): anything asking
    for a specific fact about the person that isn't in their profile —
    current employer/company, job title, a specific tool/software they
    personally use, dietary/allergy/accessibility needs, contact info, a
    yes/no personal status (visa, job-seeking), or any choice describing
    them specifically rather than their intent for this event.

    Returns {question_text: answer} — keyed by the field's original question
    (its "note"), the SAME key format generate_answers() above already uses
    for "Custom question answers" — for ONLY the fields classified "opinion".
    Callers should feed this into a FRESH registration attempt (merged into
    the `answers` passed to register_for_event) rather than trying to
    inject it into an already-running browser session via a mid-task
    "resume" message: in practice the agent doesn't reliably act on new
    values handed to it mid-session (it's been observed reporting a field
    as still-unknown even immediately after being given its answer), while
    it reliably fills in "Custom question answers" when they're part of the
    task from the very first prompt.
    """
    if not missing_fields:
        return {}

    fields_list = "\n".join(
        f'{i + 1}. field_name="{f.get("field_name", "")}" question="{f.get("note", "")}"'
        + (f" options={f.get('options')}" if f.get("options") else "")
        for i, f in enumerate(missing_fields)
    )

    prompt = f"""You are helping {profile.full_name()} register for a hackathon/event.

User profile:
{profile_to_context(profile)}

Event: {event_title}
{f"About: {event_description[:500]}" if event_description else ""}

The registration form asked some questions that don't match anything in this
person's profile. For EACH one, decide:
  - "opinion": an open-ended, forward-looking question about what they want to
    explore/build/try/discuss AT THIS EVENT (e.g. "what would you like to
    build?", "which topic are you most interested in?"). Safe to answer in
    the person's authentic voice based on their role/skills/bio — this is
    NOT a fact you'd need to already know about them.
  - "personal_fact": asks for a specific fact ABOUT the person that isn't in
    their profile — current employer/company, job title, a specific tool/
    software they personally use, dietary/allergy/accessibility needs,
    contact info, a yes/no personal status (e.g. visa, job-seeking), or any
    choice that describes them specifically rather than their intent for
    this event. NEVER guess these — always ask the human.

Questions:
{fields_list}

For every question classified "opinion", write a concise (1-2 sentence),
authentic, first-person answer matching their background and this event's
theme. If it has options, your answer must be exactly one of the given
options, verbatim (case-sensitive match).

Return ONLY a JSON object:
{{"1": {{"type": "opinion", "answer": "..."}}, "2": {{"type": "personal_fact", "answer": null}}, ...}}"""

    try:
        resp = httpx.post(
            f"{ASI_ONE_BASE_URL}/chat/completions",
            json={
                "model": ASI_ONE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.5,
            },
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*", "", content).rstrip("```").strip()
        classified = json.loads(content)

        result = {}
        for i, f in enumerate(missing_fields):
            entry = classified.get(str(i + 1)) or {}
            question = f.get("note") or f.get("field_name") or ""
            if entry.get("type") == "opinion" and entry.get("answer") and question:
                result[question] = str(entry["answer"])
        return result
    except Exception as e:
        print(f"  [ANSWERS] Field classification/generation failed: {e}")
        return {}

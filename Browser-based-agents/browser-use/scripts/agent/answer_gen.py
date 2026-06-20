"""
Generate answers to hackathon registration questions using ASI:One.

Takes the event's stored `questions` list + the user's profile and
returns a dict mapping question text → answer string.

This runs BEFORE browser-use opens the browser, so the agent has
pre-generated answers ready to paste — no LLM calls needed mid-form.
"""

import json
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL, ASI_ONE_MODEL
from agent.profile import UserProfile, profile_to_context


# Preset question types we can answer directly from profile fields
PRESET_MAP = {
    "linkedin":  lambda p: p.linkedin_url,
    "github":    lambda p: p.github_url,
    "twitter":   lambda p: p.twitter_url(),
    "email":     lambda p: p.email,
    "name":      lambda p: p.full_name(),
    "firstname": lambda p: p.first_name,
    "lastname":  lambda p: p.last_name,
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
            answers[question_text] = "yes" if profile.looking_for_job else "no"
        elif "visa" in q_lower:
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
        f"{i+1}. {q['question']}{' (required)' if q.get('required') else ' (optional)'}"
        for i, q in enumerate(questions)
    )

    prompt = f"""You are helping {profile.full_name()} register for a hackathon.

User profile:
{profile_to_context(profile)}

Event: {event_title}
{f'About: {event_description[:500]}' if event_description else ''}

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

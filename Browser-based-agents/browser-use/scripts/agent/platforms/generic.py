"""
Generic registration handler using browser-use + ASI:One.

Used for: Luma, Eventbrite, Devpost, Partiful, ETHGlobal, Devfolio,
and any other platform without a dedicated handler.

browser-use drives the browser with natural language instructions.
We give it the pre-generated answers so it doesn't need to reason
about what to write — just where to put it.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserProfile
from config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL


def _get_llm():
    """ASI:One via OpenAI-compatible interface."""
    return ChatOpenAI(
        model="asi1-mini",
        api_key=ASI_ONE_API_KEY,
        base_url=ASI_ONE_BASE_URL,
        temperature=0,
    )


async def register(
    event_url: str,
    profile,
    answers: dict[str, str],
    event_title: str = "",
    headless: bool = False,
) -> dict:
    """
    Use browser-use to register for any event.
    Returns {"success": bool, "message": str}
    """
    task = _build_task(event_url, profile, answers, event_title)

    browser = Browser(browser_profile=BrowserProfile(headless=headless))

    try:
        agent = Agent(
            task=task,
            llm=_get_llm(),
            browser=browser,
            max_failures=3,
            use_vision=True,
        )
        result = await agent.run(max_steps=25)
        success = _check_result(result)
        return {
            "success": success,
            "message": str(result)[:500],
            "final_url": "",
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        await browser.close()


def _build_task(
    event_url: str,
    profile,
    answers: dict[str, str],
    event_title: str,
) -> str:
    """Build the natural language task for browser-use."""

    # Format answers as a numbered list
    answers_text = "\n".join(
        f"  - If asked '{q}': answer with '{a}'"
        for q, a in answers.items()
        if a
    )

    # Build standard field mappings
    standard = f"""
Standard fields to fill:
  - Name / Full name: {profile.full_name()}
  - First name: {profile.first_name}
  - Last name: {profile.last_name}
  - Email: {profile.email}
  - LinkedIn: {profile.linkedin_url}
  - GitHub: {profile.github_url}
  - Twitter / X: {profile.twitter_handle}
  - Location / City: {profile.location_str()}
"""

    task = f"""Register for the hackathon "{event_title}" at {event_url}.

{standard}
{f'Custom question answers:{chr(10)}{answers_text}' if answers_text else ''}

Instructions:
1. Go to {event_url}
2. Find and click the registration/apply/RSVP button
3. If a sign-in is required with email, use {profile.luma_email or profile.email}
4. Fill in all form fields using the information above
5. For any checkbox asking to agree to terms or conditions, check it
6. For any question not listed above, give a reasonable answer based on:
   - Role: {profile.role}
   - Skills: {', '.join(profile.skills[:5])}
   - Bio: {profile.bio[:200] if profile.bio else 'Software engineer interested in AI'}
7. Submit the form
8. Confirm that registration was successful

Do NOT proceed if the event requires payment — stop and report that.
Do NOT fill in credit card or payment information.
"""
    return task


def _check_result(result) -> bool:
    """Check if browser-use completed successfully."""
    result_str = str(result).lower()
    failure_signals = ["failed", "error", "could not", "unable", "payment required"]
    success_signals = ["success", "registered", "submitted", "confirmed", "applied", "rsvp"]

    if any(s in result_str for s in failure_signals):
        return False
    if any(s in result_str for s in success_signals):
        return True
    return True  # assume success if no explicit failure

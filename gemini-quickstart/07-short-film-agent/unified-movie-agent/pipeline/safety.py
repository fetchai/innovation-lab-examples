"""
Upfront content-safety check using Gemini Flash.
Returns (is_safe, reason). Defaults to safe=True on infra errors.
"""

import logging
from google import genai
from google.genai import types

from config import SAFETY_KEY, SAFETY_MODEL

log = logging.getLogger(__name__)

_client = genai.Client(api_key=SAFETY_KEY)

SAFETY_PROMPT = """You are a content safety evaluator for a video generation system (Google Veo).
Evaluate whether the following user prompt is safe to use for AI video generation.

A prompt is UNSAFE if it requests:
- Violence, gore, weapons, or harm to people/animals
- Sexually explicit or suggestive content
- Hate speech, discrimination, or harassment
- Illegal activities or dangerous instructions
- Content involving minors in inappropriate contexts
- Deepfakes or impersonation of real people
- Copyrighted characters or content that would violate IP

Respond with EXACTLY one line in this format:
SAFE: <brief reason>
or
UNSAFE: <brief reason explaining why>

User prompt to evaluate:
"{prompt}"
"""


async def check_prompt_safety(prompt: str) -> tuple[bool, str]:
    """
    Use Gemini Flash to evaluate prompt safety.
    Returns (is_safe, reason).
    Falls back to safe=True if the check itself fails.
    """
    try:
        response = _client.models.generate_content(
            model=SAFETY_MODEL,
            contents=SAFETY_PROMPT.format(prompt=prompt),
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=100,
            ),
        )

        result = response.text.strip()

        if result.upper().startswith("UNSAFE"):
            reason = (
                result.split(":", 1)[1].strip()
                if ":" in result
                else "Content policy violation"
            )
            return False, reason
        elif result.upper().startswith("SAFE"):
            return True, ""
        else:
            return True, "Could not parse safety response; allowing"

    except Exception as e:
        log.warning("Safety check error (%s); allowing by default", e)
        return True, f"Safety check error ({e}); allowing by default"

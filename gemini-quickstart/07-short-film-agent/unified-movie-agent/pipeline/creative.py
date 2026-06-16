"""
Creative Director: turns a user prompt into an 8-scene story plan.
Uses Gemini Flash for fast, cheap planning.
"""

import json
import re
import logging
from typing import List, Dict, Any

from google import genai

from config import CREATIVE_KEY, CREATIVE_MODEL, SCENE_COUNT
from models import SceneBrief, StoryPlan

log = logging.getLogger(__name__)

_client = genai.Client(api_key=CREATIVE_KEY)


# ── Text helpers ────────────────────────────────────────────────


def _clean(text: str) -> str:
    if text is None:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"^\s*[-*]\s*", "", text)
    text = re.sub(r"^\s*scene\s*\d+\s*[:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*\d+\s*[:.\)\-]\s*", "", text)
    text = text.strip().strip('"').strip("'").strip()
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, max_words: int = 16) -> str:
    text = _clean(text)
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",;:")


def _fallback_scene(index: int, story: str) -> Dict[str, Any]:
    base = _clean(story) or "A human and AI work together to improve the world."
    if index == 1:
        v = f"Introduce the main human character and their world, inspired by: {base}"
        m = "Gentle, curious intro music with light hope"
        t = "I did not expect this day to change everything."
    elif index == SCENE_COUNT:
        v = f"Final wide shot showing lasting impact of their journey, inspired by: {base}"
        m = "Warm, uplifting finale with a sense of closure"
        t = "Together we proved the future can be kinder and brighter."
    else:
        v = f"Human and AI collaborate on a key moment in the journey, inspired by: {base}"
        m = "Steady, hopeful underscore with subtle momentum"
        t = "Side by side, we keep pushing the world forward."
    return {
        "scene_index": index,
        "scene_title": f"Scene {index}",
        "visual_prompt": v,
        "music_prompt": m,
        "voiceover_prompt": t,
        "duration_seconds": 8,
    }


# ── Gemini prompt ───────────────────────────────────────────────


def _build_prompt(user_prompt: str, refs: List[str]) -> str:
    refs_str = json.dumps(refs or [], ensure_ascii=False)
    return f"""
You are a world-class cinematic creative director for short AI-generated films.

Your task:
- Create a brief story_title (3-5 words)
- Create a story_logline (one sentence summarizing the full arc)
- Turn the user's story idea into EXACTLY {SCENE_COUNT} scenes.
- Each scene must have:
  - scene_index (1..{SCENE_COUNT})
  - scene_title: A brief 2-4 word title for the scene
  - visual_prompt: ONE SHORT sentence describing visuals for Veo (max 25 words).
    - **IMPORTANT**: Veo will use {len(refs or [])} reference image(s) for character consistency: {refs_str}
    - **CHARACTER DESCRIPTIONS IN VISUAL PROMPTS**: Veo matches reference images to characters by comparing the image content to descriptive text in the prompt. Therefore, NEVER use character names (e.g., "Oliver", "Buddy") in visual_prompt. ALWAYS use detailed physical descriptions instead (e.g., "a fat orange tabby cat", "a small golden retriever puppy", "a short cheerful gnome with a red hat"). Include species, size, coloring, and distinguishing features EVERY time a character appears. This is critical for Veo to correctly match each reference image to the right character.
    - Character names (e.g., "Oliver", "Buddy") are ONLY allowed in voiceover_prompt, NOT in visual_prompt.
    - Be cinematic and specific, but EXTREMELY concise.
    - **EVERY visual prompt MUST describe characters IN MOTION — an active verb showing movement or action.** Static poses like "standing", "looking", "freezing", "peering" produce bad video. Instead use dynamic verbs: "sprinting", "leaping", "climbing", "dodging", "sliding", "charging", "tumbling", "reaching", "pulling", "swimming". Even quiet scenes need subtle motion: "gently walking", "slowly turning", "carefully stepping".
    - Use VARIED and DYNAMIC camera work across all 8 scenes. Choose from: wide shot, close-up, dolly shot, tracking shot, crane shot, handheld shot, POV shot, aerial shot, low-angle shot, over-the-shoulder shot, slow zoom, whip pan. Do NOT repeat the same camera type in consecutive scenes.
    - Use clear, descriptive language - avoid vague terms like "strange", "mysterious", or "eerie".
    - NO instructions, no "we see", no narration—just describe what's visible.
    - Describe WHO, WHAT they're DOING (active verb), WHERE (setting), and camera angle.
    - Do NOT include scene numbers, notes, or meta-instructions.
  - music_prompt: a SHORT phrase with tempo + genre + instruments. Examples:
      "90bpm warm hopeful piano with soft strings"
      "120bpm tense dark synth with reverb kicks"
      "70bpm gentle acoustic guitar with ambient pads"
      "140bpm fast orchestral brass with driving percussion"
    - Always include approximate tempo (bpm), at least one instrument, and mood.
    - No long sentences, no explanations.
  - voiceover_prompt: EXACTLY one complete sentence, 12-16 words.
    - This is what a narrator will speak in exactly 8 seconds.
    - MUST be 12-16 words. Count carefully. NEVER end mid-sentence or with incomplete thoughts.
    - Vary the emotional tone across scenes: excited, hushed, tense, awed, warm, urgent, reflective, triumphant. Do NOT use the same epic/reflective tone for every scene.
    - No quotes, no scene numbers, no 'Scene 1', no notes.
    - Plain English sentence only.
  - duration_seconds: Always 8

Story arc (universal — works for ANY theme or genre):
- Scene 1: Establish the main character(s), their world, and their normal situation.
- Scene 2: Introduce the central hook — a discovery, encounter, or inciting event that disrupts the status quo.
- Scene 3: Show the characters' first bold step into the unknown — exploration, collaboration, or pursuit.
- Scene 4: Present a challenge, conflict, or obstacle that raises the stakes.
- Scene 5: Show a creative, surprising, or resourceful response that demonstrates the characters' strengths.
- Scene 6: Expand the impact — the consequences ripple outward, affecting others or revealing something bigger.
- Scene 7: Climactic confrontation or peak dramatic moment — the highest tension, the ultimate test.
- Scene 8: Resolution — victory, transformation, or emotional closure. End with a sense of completion.

GLOBAL RULES:
- OUTPUT MUST BE **VALID JSON ONLY**.
- DO NOT wrap the JSON in markdown code blocks (```json).
- DO NOT include any text before or after the JSON.
- Return ONLY the raw JSON object.
- JSON structure MUST be:

{{
  "status": "ok",
  "story_title": "A brief title for the story",
  "story_logline": "One sentence describing the full story arc",
  "scenes": [
    {{
      "scene_index": 1,
      "scene_title": "Brief scene title",
      "visual_prompt": "...",
      "music_prompt": "...",
      "voiceover_prompt": "...",
      "duration_seconds": 8
    }},
    ...
  ]
}}

- Do NOT include any other top-level keys.
- scenes MUST be an array of exactly {SCENE_COUNT} objects.
- scene_index MUST be integers 1 through {SCENE_COUNT}.

**REFERENCE IMAGE GUIDANCE:**
Reference images are provided for character consistency. Veo matches reference images to characters by comparing the image content to the physical descriptions in the visual_prompt text:
- ALWAYS use the SAME detailed physical description for each character across ALL scenes (e.g., "a fat orange tabby cat" in every scene, not "Oliver" or "the cat")
- Include species/type, size, coloring, and key features each time
- Example: If there's a cat, a puppy, and a gnome, write: "a fat orange tabby cat leaps over a log while a small golden retriever puppy splashes through a stream and a short cheerful gnome with a red pointed hat pulls vines aside"
- NEVER use just names or vague references like "the trio", "the group", "the friends", "the companions" — Veo cannot understand these
- Voiceover can use character names freely — only visual_prompt requires physical descriptions

User story (use this as the thematic core, but keep prompts concise and production-ready):

\"\"\"{user_prompt}\"\"\""""


def _parse_json(raw: str) -> Dict[str, Any]:
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise


def _normalize(data: Dict[str, Any], story: str) -> List[SceneBrief]:
    raw_scenes = data.get("scenes", [])
    if not isinstance(raw_scenes, list):
        raw_scenes = []

    raw_scenes = sorted(raw_scenes, key=lambda s: int(s.get("scene_index", 999)))
    briefs: List[SceneBrief] = []

    for i, s in enumerate(raw_scenes[:SCENE_COUNT]):
        idx = max(1, min(SCENE_COUNT, int(s.get("scene_index", i + 1))))
        vp = (
            _clean(str(s.get("visual_prompt", s.get("video_prompt", ""))))
            or "Visualize a key moment from the story."
        )
        mp = (
            _clean(str(s.get("music_prompt", "")))
            or "Cinematic, hopeful underscore with gentle forward motion"
        )
        vt = (
            _truncate(str(s.get("voiceover_prompt", s.get("voiceover_text", ""))))
            or "Side by side, we turn this idea into something real."
        )

        briefs.append(
            SceneBrief(
                scene_index=idx,
                scene_title=_clean(str(s.get("scene_title", f"Scene {idx}"))),
                visual_prompt=vp,
                music_prompt=mp,
                voiceover_prompt=vt,
                duration_seconds=int(s.get("duration_seconds", 8)),
            )
        )

    while len(briefs) < SCENE_COUNT:
        fb = _fallback_scene(len(briefs) + 1, story)
        briefs.append(SceneBrief(**fb))

    # Re-index 1..N
    for i, b in enumerate(briefs):
        b.scene_index = i + 1

    return briefs


# ── Public API ──────────────────────────────────────────────────


async def plan_story(user_prompt: str, ref_urls: List[str]) -> StoryPlan:
    """
    Call Gemini Flash and return a StoryPlan with 8 SceneBriefs.
    Falls back to generic scenes on any error.
    """
    try:
        prompt = _build_prompt(user_prompt, ref_urls)
        response = _client.models.generate_content(
            model=CREATIVE_MODEL,
            contents=prompt,
        )
        data = _parse_json(response.text.strip())
        scenes = _normalize(data, user_prompt)

        return StoryPlan(
            title=data.get("story_title", "AI Story"),
            logline=data.get("story_logline", user_prompt[:100]),
            scenes=scenes,
            status=data.get("status", "ok"),
        )

    except Exception as e:
        log.error("Creative Director error: %s — using fallbacks", e)
        fallback_scenes = [
            SceneBrief(**_fallback_scene(i, user_prompt))
            for i in range(1, SCENE_COUNT + 1)
        ]
        return StoryPlan(
            title="AI Story (Fallback)",
            logline=user_prompt[:100]
            if user_prompt
            else "A story about humans and AI.",
            scenes=fallback_scenes,
            status="fallback",
            error=str(e),
        )

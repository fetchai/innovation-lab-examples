"""
Pipeline orchestrator: drives the full film production as async functions.

Flow:
  1. Safety check
  2. Creative Director → 8-scene plan
  3. For each scene (all 8 in parallel):
     - Video (Veo) + TTS + Music in parallel
     - Assembly (FFmpeg merge)
  4. Opening + Closing videos (parallel with scenes)
  5. Story stitch (FFmpeg concat all)
  6. Return final FilmResult

The caller (main.py) can send progress updates to the user at each callback.
"""

import asyncio
import logging
from typing import Callable, Awaitable, Optional, List

from config import SCENE_COUNT, SCENE_DURATION_SECONDS, MAX_RETRIES
from models import SceneBrief, StoryPlan, SceneResult, FilmResult
from utils.retry import with_retry

from pipeline import safety, creative, video, tts, music, assembly, stitcher, chargen

log = logging.getLogger(__name__)

# Type alias for the progress-notification callback.
# The orchestrator calls  `await notify(message)`  whenever there's user-facing news.
Notify = Callable[[str], Awaitable[None]]


async def _noop(_msg: str) -> None:
    """Default no-op notifier (used when caller doesn't provide one)."""
    pass


# ── Per-scene pipeline ──────────────────────────────────────────


async def _produce_scene(
    brief: SceneBrief,
    ref_urls: List[str],
    notify: Notify,
) -> SceneResult:
    """
    Generate video + voice + music for one scene, then assemble.
    All three media types run in parallel; assembly runs after all three finish.
    Uses retry wrapper for each step.
    """
    idx = brief.scene_index  # 1-based
    idx0 = idx - 1  # 0-based (for key assignment)
    result = SceneResult(scene_index=idx, scene_title=brief.scene_title)

    try:
        # --- Generate video / voice / music in parallel ---
        (
            video_url,
            (voice_url, voice_dur),
            (music_url, music_dur),
        ) = await asyncio.gather(
            with_retry(
                video.generate_scene_video,
                scene_index=idx0,
                prompt=brief.visual_prompt,
                ref_urls=ref_urls,
                max_retries=MAX_RETRIES,
                label=f"video-scene-{idx}",
            ),
            with_retry(
                tts.generate_voice,
                scene_index=idx0,
                text=brief.voiceover_prompt,
                max_retries=MAX_RETRIES,
                label=f"tts-scene-{idx}",
            ),
            with_retry(
                music.generate_music,
                scene_index=idx0,
                prompt=brief.music_prompt,
                duration=SCENE_DURATION_SECONDS,
                max_retries=MAX_RETRIES,
                label=f"music-scene-{idx}",
            ),
        )

        result.video_url = video_url
        result.voice_url = voice_url
        result.music_url = music_url

        log.info("Scene %d/%d — all assets ready, assembling…", idx, SCENE_COUNT)

        # --- Assemble ---
        assembled_url, assembled_dur = await with_retry(
            assembly.assemble_scene,
            scene_index=idx0,
            video_url=video_url,
            voice_url=voice_url,
            music_url=music_url,
            max_retries=MAX_RETRIES,
            label=f"assembly-scene-{idx}",
        )
        result.assembled_url = assembled_url

        log.info("Scene %d/%d assembled: %s", idx, SCENE_COUNT, assembled_url)

    except Exception as e:
        result.error = str(e)[:300]
        log.error("Scene %d failed: %s", idx, result.error)
        await notify(f"❌ Scene {idx}/{SCENE_COUNT} failed: {result.error}")

    return result


# ── Full pipeline ───────────────────────────────────────────────


async def produce_film(
    user_prompt: str,
    ref_urls: Optional[List[str]] = None,
    notify: Notify = _noop,
) -> FilmResult:
    """
    Run the entire film production pipeline.
    Returns a FilmResult with per-scene URLs and the final stitched URL.
    Calls `notify` with markdown-formatted progress messages.
    """
    ref_urls = ref_urls or []

    # ── 1. Safety check (silent — no user notification) ─────────
    log.info("Running safety check…")
    is_safe, reason = await safety.check_prompt_safety(user_prompt)
    if not is_safe:
        log.warning("Prompt rejected: %s", reason)
        return FilmResult(
            title="",
            logline="",
            scenes=[],
            error=f"Content policy violation: {reason}",
        )
    log.info("Safety check passed")

    # ── 2. Creative Director ────────────────────────────────────
    await notify(
        "🎨 Creative Director is planning your 8-scene story arc...\n"
        "⏳ This will take ~15 seconds"
    )
    plan: StoryPlan = await creative.plan_story(user_prompt, ref_urls)

    summary = f"📖 **{plan.title}**\n🧵 {plan.logline}\n\n**Scene Briefs:**\n\n"
    for sb in plan.scenes:
        summary += (
            f"**Scene {sb.scene_index}: {sb.scene_title}**\n"
            f"🎥 Video: {sb.visual_prompt}\n"
            f"🎵 Music: {sb.music_prompt}\n"
            f"🎤 Voiceover: {sb.voiceover_prompt}\n\n"
        )
    await notify(summary)

    # ── 2b. Auto-generate character refs if user provided none ──
    if not ref_urls:
        await notify(
            "🎭 Generating character references for visual consistency...\n"
            "⏳ ~15 seconds"
        )
        scene_visual_prompts = [s.visual_prompt for s in plan.scenes]
        auto_refs = await chargen.generate_character_refs(
            plan.title,
            plan.logline,
            scene_visual_prompts,
        )
        if auto_refs:
            ref_urls = auto_refs
            log.info("Using %d auto-generated character references", len(ref_urls))
        else:
            log.info("No auto-generated refs — proceeding without reference images")

    # ── 3. All scenes + opening/closing in parallel ─────────────
    await notify(
        "🎬 Production starting... Generating video, music, and voiceover for each scene\n"
        "⏳ Estimated time: ~90 seconds\n"
        "🎬 Movie Production Started!"
    )

    # Scene tasks
    scene_coros = [_produce_scene(brief, ref_urls, notify) for brief in plan.scenes]
    # Opening / closing tasks
    opening_coro = with_retry(
        video.generate_opening,
        title=plan.title,
        logline=plan.logline,
        ref_urls=ref_urls,
        max_retries=MAX_RETRIES,
        label="opening",
    )
    closing_coro = with_retry(
        video.generate_closing,
        title=plan.title,
        max_retries=MAX_RETRIES,
        label="closing",
    )

    # Run everything concurrently
    results = await asyncio.gather(
        asyncio.gather(*scene_coros),
        opening_coro,
        closing_coro,
        return_exceptions=True,
    )

    scene_results: List[SceneResult] = (
        results[0] if not isinstance(results[0], Exception) else []
    )
    opening_url: Optional[str] = (
        results[1] if not isinstance(results[1], Exception) else None
    )
    closing_url: Optional[str] = (
        results[2] if not isinstance(results[2], Exception) else None
    )

    if isinstance(results[0], Exception):
        log.error("Scene batch failed: %s", results[0])
    if isinstance(results[1], Exception):
        log.error("Opening failed: %s", results[1])
    if isinstance(results[2], Exception):
        log.error("Closing failed: %s", results[2])

    if opening_url:
        log.info("Opening title ready: %s", opening_url)
    if closing_url:
        log.info("Closing credits ready: %s", closing_url)

    # ── 4. Check for fatal scene failures ───────────────────────
    assembled_urls = [s.assembled_url for s in scene_results]
    failed = [s for s in scene_results if not s.assembled_url]
    if failed:
        fail_nums = ", ".join(str(s.scene_index) for s in failed)
        err_msg = f"Scenes {fail_nums} failed — cannot stitch final movie."
        await notify(f"🛑 **Film aborted.** {err_msg}")
        return FilmResult(
            title=plan.title,
            logline=plan.logline,
            scenes=scene_results,
            opening_url=opening_url,
            closing_url=closing_url,
            error=err_msg,
        )

    # ── 5. Stitch ───────────────────────────────────────────────
    log.info("Stitching all scenes into the final movie…")
    try:
        final_url = await stitcher.stitch_story(
            scene_urls=assembled_urls,
            opening_url=opening_url,
            closing_url=closing_url,
        )
    except Exception as e:
        err = f"Story stitch failed: {e}"
        log.error(err)
        await notify(f"❌ {err}")
        return FilmResult(
            title=plan.title,
            logline=plan.logline,
            scenes=scene_results,
            opening_url=opening_url,
            closing_url=closing_url,
            error=err,
        )

    return FilmResult(
        title=plan.title,
        logline=plan.logline,
        scenes=scene_results,
        opening_url=opening_url,
        closing_url=closing_url,
        final_url=final_url,
    )

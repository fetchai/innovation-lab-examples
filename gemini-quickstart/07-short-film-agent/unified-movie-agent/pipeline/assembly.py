"""
FFmpeg per-scene assembly: merge video + voiceover + background music.
Downloads media from GCS URLs, adjusts durations, mixes audio, uploads result.
"""

import re
import shutil
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx

from utils.gcs import upload_to_storage

log = logging.getLogger(__name__)

TEMP_DIR = Path("./temp_assembly")
TEMP_DIR.mkdir(exist_ok=True)


# ── Helpers ──────────────────────────────────────────────────────


async def _download(url: str, path: Path) -> Path:
    async with httpx.AsyncClient(timeout=300.0) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def _duration(media_path: Path) -> float:
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", str(media_path), "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        m = re.search(
            r"Duration: (\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)", result.stderr or ""
        )
        if not m:
            return 0.0
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        return 0.0


def _adjust_duration(audio: Path, target: float, out: Path) -> Path:
    current = _duration(audio)
    if current == 0:
        raise ValueError(f"Cannot get duration for {audio}")
    if abs(current - target) < 1.0:
        return audio
    if current < target:
        cmd = [
            "ffmpeg",
            "-i",
            str(audio),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-filter_complex",
            "[0:a][1:a]concat=n=2:v=0:a=1[out]",
            "-map",
            "[out]",
            "-t",
            str(target),
            "-y",
            str(out),
        ]
    else:
        cmd = ["ffmpeg", "-i", str(audio), "-t", str(target), "-y", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def _combine(video: Path, voice: Path, music: Path, out: Path) -> Path:
    cmd = [
        "ffmpeg",
        "-i",
        str(video),
        "-i",
        str(voice),
        "-i",
        str(music),
        "-filter_complex",
        "[1:a]volume=1.0[voice];[2:a]volume=0.5[music];"
        "[voice][music]amix=inputs=2:duration=first[audio]",
        "-map",
        "0:v",
        "-map",
        "[audio]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-y",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg merge failed: {result.stderr[:300]}")
    return out


# ── Public API ──────────────────────────────────────────────────


async def assemble_scene(
    scene_index: int,
    video_url: str,
    voice_url: str,
    music_url: str,
) -> tuple[str, float]:
    """
    Download video+voice+music, merge, upload.
    Returns (gcs_url, duration_seconds).
    """
    work = TEMP_DIR / f"scene_{scene_index}_{uuid4().hex[:6]}"
    work.mkdir(exist_ok=True)

    try:
        log.info("Assembly scene %d — downloading assets…", scene_index)
        video_p = await _download(video_url, work / "video.mp4")
        voice_p = await _download(voice_url, work / "voice.wav")
        music_p = await _download(music_url, work / "music.wav")

        target = _duration(video_p)
        log.info("Scene %d durations: video=%.1fs", scene_index, target)

        voice_adj = _adjust_duration(voice_p, target, work / "voice_adj.wav")
        music_adj = _adjust_duration(music_p, target, work / "music_adj.wav")

        out = _combine(video_p, voice_adj, music_adj, work / "final.mp4")
        dur = _duration(out)

        with open(out, "rb") as f:
            data = f.read()
        fname = f"assembled_{int(datetime.now().timestamp())}_{uuid4().hex[:8]}.mp4"
        url = upload_to_storage(data, fname, "video/mp4")
        log.info("Assembly scene %d uploaded: %s (%.1fs)", scene_index, url, dur)
        return url, dur

    finally:
        shutil.rmtree(work, ignore_errors=True)

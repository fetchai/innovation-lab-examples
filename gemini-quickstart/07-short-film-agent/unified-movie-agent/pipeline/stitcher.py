"""
FFmpeg story stitcher: concatenate opening + 8 scenes + closing into one video.
Uses concat filter with re-encoding to handle mixed audio/video parameters.
"""

import shutil
import subprocess
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from typing import List

import httpx

from utils.gcs import upload_to_storage

log = logging.getLogger(__name__)


async def _download(url: str, path: Path) -> Path:
    async with httpx.AsyncClient(timeout=300.0) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def _concat_ffmpeg(paths: List[Path], out: Path) -> None:
    parts = "".join(f"[{i}:v][{i}:a]" for i in range(len(paths)))
    filt = f"{parts}concat=n={len(paths)}:v=1:a=1[outv][outa]"

    cmd = ["ffmpeg", "-loglevel", "warning"]
    for p in paths:
        cmd.extend(["-i", str(p)])
    cmd.extend(
        [
            "-filter_complex",
            filt,
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            "-y",
            str(out),
        ]
    )

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed: {result.stderr[:300]}")


# ── Public API ──────────────────────────────────────────────────


async def stitch_story(
    scene_urls: List[str],
    opening_url: str | None = None,
    closing_url: str | None = None,
) -> str:
    """
    Download all videos, concatenate [opening + scenes + closing], upload.
    Returns the final GCS URL.
    """
    tmp = Path(tempfile.mkdtemp(prefix="stitch_"))

    try:
        all_urls: List[str] = []
        if opening_url:
            all_urls.append(opening_url)
        all_urls.extend(scene_urls)
        if closing_url:
            all_urls.append(closing_url)

        log.info("Stitching %d videos…", len(all_urls))
        local: List[Path] = []
        for i, url in enumerate(all_urls):
            p = tmp / f"part_{i}.mp4"
            await _download(url, p)
            local.append(p)
            log.info("  Downloaded %d/%d", i + 1, len(all_urls))

        out = tmp / "final_story.mp4"
        _concat_ffmpeg(local, out)
        log.info("Concat complete")

        with open(out, "rb") as f:
            data = f.read()
        fname = f"final_story_{int(datetime.now().timestamp())}_{uuid4().hex[:8]}.mp4"
        url = upload_to_storage(data, fname, "video/mp4")
        log.info("Final story uploaded: %s", url)
        return url

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

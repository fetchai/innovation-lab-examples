import os
import requests  # type: ignore[import-untyped]
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from uagents import Agent, Context
from shared_models import TranscriptRequest, TranscriptResponse

load_dotenv()

agent = Agent(
    name="transcript_agent",
    seed=os.getenv("TRANSCRIPT_SEED"),
    port=8005,
    endpoint=[os.getenv("TRANSCRIPT_ENDPOINT", "http://localhost:8005/submit")],
    network="testnet",
)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def extract_video_id(url: str):
    try:
        parsed = urlparse(url)
        if parsed.hostname == "youtu.be":
            return parsed.path[1:]
        if parsed.hostname in ("www.youtube.com", "youtube.com"):
            return parse_qs(parsed.query).get("v", [None])[0]
    except Exception:
        return None
    return None


def get_video_metadata(video_id: str) -> dict:
    try:
        url = (
            f"https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}"
        )
        resp = requests.get(url, timeout=10).json()
        items = resp.get("items", [])
        if not items:
            return {}
        snippet = items[0]["snippet"]
        return {
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "thumbnail_url": (
                snippet.get("thumbnails", {}).get("high", {}).get("url", "")
            ),
            "published_at": snippet.get("publishedAt", ""),
        }
    except Exception:
        return {}


@agent.on_message(TranscriptRequest)
async def handle_transcript(ctx: Context, sender: str, msg: TranscriptRequest):
    ctx.logger.info(f"Transcript request for: {msg.youtube_url}")

    video_id = extract_video_id(msg.youtube_url)
    if not video_id:
        await ctx.send(
            sender,
            TranscriptResponse(
                success=False,
                error="Invalid YouTube URL — expected youtube.com/watch?v=... or youtu.be/...",
            ),
        )
        return

    metadata = get_video_metadata(video_id)
    ctx.logger.info(
        f"Metadata: '{metadata.get('title')}' by '{metadata.get('channel')}'"
    )

    try:
        # youtube-transcript-api >= 1.0 replaced the static `get_transcript`
        # with an instance method `fetch` that returns a FetchedTranscript
        # (iterable of FetchedTranscriptSnippet with .text / .start / .duration).
        fetched = YouTubeTranscriptApi().fetch(
            video_id, languages=["en", "en-US", "en-GB"]
        )
        transcript = " ".join(snippet.text for snippet in fetched)
        ctx.logger.info(f"Transcript fetched: {len(transcript):,} chars")
        await ctx.send(
            sender,
            TranscriptResponse(
                success=True,
                transcript=transcript,
                video_title=metadata.get("title", ""),
                channel_name=metadata.get("channel", ""),
                thumbnail_url=metadata.get("thumbnail_url", ""),
            ),
        )
    except (TranscriptsDisabled, NoTranscriptFound):
        await ctx.send(
            sender,
            TranscriptResponse(
                success=False,
                error="No English captions available on this video.",
                video_title=metadata.get("title", ""),
                channel_name=metadata.get("channel", ""),
            ),
        )
    except Exception as e:
        ctx.logger.error(f"Transcript error: {e}")
        await ctx.send(sender, TranscriptResponse(success=False, error=str(e)))


if __name__ == "__main__":
    agent.run()

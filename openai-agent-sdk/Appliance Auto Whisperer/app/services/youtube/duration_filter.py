from app.models.tutorial import VideoHit


def filter_by_duration_placeholder(
    videos: list[VideoHit],
    *,
    min_seconds: int | None = None,
    max_seconds: int | None = None,
) -> list[VideoHit]:
    """YouTube duration requires videos.list; stub returns input."""
    _ = (min_seconds, max_seconds)
    return videos

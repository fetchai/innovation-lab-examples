from app.models.tutorial import VideoHit
from app.services.youtube.ranking import score_videos


def test_score_videos_order() -> None:
    v = [
        VideoHit(title="a", video_id="1", url="u1"),
        VideoHit(title="b", video_id="2", url="u2"),
    ]
    out = score_videos(v)
    assert out[0].score >= out[1].score

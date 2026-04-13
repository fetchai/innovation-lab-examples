from app.models.tutorial import VideoHit


def score_videos(videos: list[VideoHit]) -> list[VideoHit]:
    out = []
    for i, v in enumerate(videos):
        out.append(v.model_copy(update={"score": float(10 - i)}))
    return out

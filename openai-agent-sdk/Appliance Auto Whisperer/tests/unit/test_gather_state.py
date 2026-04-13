from app.uagents_protocol.gather_state import (
    initial_gather,
    is_gather_complete,
    with_scrape,
    with_video,
)


def test_gather_complete_when_both() -> None:
    g = initial_gather(
        vision={"part_name": "x", "part_number": "y", "estimated_labor_cost": 200.0},
        user_session_id="s1",
        reply_to="addr1",
    )
    g = with_scrape(g, {"price_usd": 18.0, "purchase_url": "u", "stock_status": "ok"})
    assert not is_gather_complete(g)
    g = with_video(g, {"video_url": "v", "video_title": "t", "duration_seconds": 120})
    assert is_gather_complete(g)

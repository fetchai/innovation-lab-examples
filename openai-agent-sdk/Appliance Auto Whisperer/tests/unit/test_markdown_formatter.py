from app.chat.markdown_formatter import synthesis_to_markdown
from app.models.synthesis import SynthesisResult


def test_synthesis_to_markdown() -> None:
    syn = SynthesisResult(
        summary="Test",
        next_steps=["Step 1"],
        estimated_cost_range=(10.0, 20.0),
    )
    structured = {
        "tutorials": {"videos": [{"title": "V", "url": "https://youtu.be/x"}]}
    }
    md = synthesis_to_markdown(syn, structured)
    assert "Test" in md
    assert "youtu.be" in md

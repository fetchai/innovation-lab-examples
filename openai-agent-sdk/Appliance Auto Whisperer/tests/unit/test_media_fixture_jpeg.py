from pathlib import Path

from app.services.media.image_loader import load_image_bytes
from app.services.media.image_validator import validate_jpeg_magic

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_fixture_jpegs_are_valid_magic() -> None:
    for name in (
        "sample_fridge_part.jpg",
        "sample_dashboard_light.jpg",
        "sample_pipe_fitting.jpg",
    ):
        data = load_image_bytes(FIXTURES / name)
        assert validate_jpeg_magic(data)

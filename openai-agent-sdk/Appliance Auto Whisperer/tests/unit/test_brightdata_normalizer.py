from app.services.brightdata.normalizer import normalize_part_label


def test_normalize_part_label() -> None:
    assert normalize_part_label("  door   seal  ") == "door seal"

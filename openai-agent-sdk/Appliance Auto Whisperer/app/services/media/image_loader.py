from pathlib import Path


def load_image_bytes(path: Path) -> bytes:
    return path.read_bytes()

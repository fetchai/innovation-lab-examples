def validate_jpeg_magic(data: bytes) -> bool:
    return len(data) >= 3 and data[:3] == b"\xff\xd8\xff"

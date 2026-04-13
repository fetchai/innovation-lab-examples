import base64


def strip_data_url(data_url_or_b64: str) -> str:
    s = data_url_or_b64.strip()
    if "," in s and s.lower().startswith("data:"):
        return s.split(",", 1)[1]
    return s


def decode_base64_image(b64: str) -> bytes:
    return base64.b64decode(strip_data_url(b64))

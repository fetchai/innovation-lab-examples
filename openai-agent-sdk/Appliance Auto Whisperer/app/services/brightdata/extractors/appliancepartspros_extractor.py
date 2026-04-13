import re


def extract_app_hints(html: str) -> list[dict[str, str]]:
    titles = re.findall(r'class="product-name"[^>]*>([^<]+)<', html)[:5]
    return [
        {"title": t.strip(), "vendor": "appliancepartspros"}
        for t in titles
        if t.strip()
    ]

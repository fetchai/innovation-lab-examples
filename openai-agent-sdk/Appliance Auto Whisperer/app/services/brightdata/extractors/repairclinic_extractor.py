import re


def extract_repairclinic_hints(html: str) -> list[dict[str, str]]:
    titles = re.findall(r'data-part-name="([^"]+)"', html)[:5]
    return [{"title": t, "vendor": "repairclinic"} for t in titles]

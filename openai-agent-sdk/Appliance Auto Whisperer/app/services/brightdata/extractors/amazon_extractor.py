import re


def extract_amazon_hints(html: str) -> list[dict[str, str]]:
    titles = re.findall(r'data-cy="title-recipe".*?>([^<]+)<', html)[:5]
    return [{"title": t.strip(), "vendor": "amazon"} for t in titles if t.strip()]

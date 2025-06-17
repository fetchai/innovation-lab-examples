import re

from .fold_to_ascii import fold, fold_without_insertion_deletion


def strip_accents(s: str, keep_length: bool = False) -> str:
    """Strip accents and normalize string.

    :param s: the string to normalize
    :param keep_length: if True, no character is replaced without a
        subtitution of length 1: the length of the string is therefore kept
        unchanged. Default to False.
    :return: the normalized string
    """
    if keep_length:
        return fold_without_insertion_deletion(s)
    else:
        return fold(s)


CONSECUTIVE_HYPHEN_REGEX = re.compile(r"-{2,}")


def strip_consecutive_hyphens(text: str) -> str:
    """Convert a sequence of 2+ hypens into a single hyphen."""
    return CONSECUTIVE_HYPHEN_REGEX.sub("-", text)


TAG_MAP_TABLE = {
    ord("œ"): "oe",
    ord(" "): "-",
    ord("'"): "-",
    ord("`"): "-",
    ord('"'): "-",
    ord("."): "-",
    ord("!"): "-",
    ord("?"): "-",
    ord("["): "-",
    ord("]"): "-",
    ord("("): "-",
    ord(")"): "-",
    ord("{"): "-",
    ord("}"): "-",
    ord("#"): "-",
    ord("$"): "-",
    ord("%"): "-",
    ord("&"): "-",
    ord("\\"): "-",
    ord("*"): "-",
    ord("+"): "-",
    ord(","): "-",
    ord("/"): "-",
    ord(";"): "-",
    ord("<"): "-",
    ord(">"): "-",
    ord("="): "-",
    ord("@"): "-",
    ord("^"): "-",
    ord("_"): "-",
    ord("|"): "-",
    ord("~"): "-",
}


def get_tag(text: str) -> str:
    """Return a tag from a text.

    In Open Food Facts, tags are obtained from free text by performing the
    following:
    - lowercasing
    - accent removal
    - replacement of punctuation by either a comma ("-") or nothing, depending
    on the punctuation

    The input text can contain a language prefix, which is kept in the output
    if present. The language prefix is a 2-letter code followed by a colon
    (e.g. "fr:").

    This function is not strictly on par with Product Opener implementation,
    but it should be good enough for most cases.
    """
    text = text.lower()
    lang_prefix = None
    if len(text) >= 3 and text[2] == ":":
        lang_prefix = text[:2]
        text = text[3:]
    text = strip_accents(text, keep_length=True)
    text = text.translate(TAG_MAP_TABLE).strip("-")
    text = strip_consecutive_hyphens(text)
    if lang_prefix:
        text = f"{lang_prefix}:{text}"
    return text


def replace_lang_prefix(tag: str, new_lang_prefix: str) -> str:
    """Replace the language prefix of a tag with a new one."""

    if len(new_lang_prefix) != 2:
        raise ValueError(
            f"new_lang_prefix '{new_lang_prefix}' must be a 2-letter code."
        )

    if len(tag) < 3 or tag[2] != ":":
        raise ValueError(f"tag '{tag}' has an invalid language prefix")

    return f"{new_lang_prefix}:{tag[3:]}"

"""Text normalization.
"""

import re
import unicodedata

import homoglyphs as hg
import regex

_URL_RE = re.compile(r"https?://\S+")
_MENTION_RE = re.compile(r"@[\w.\-]+")
_HASHTAG_RE = re.compile(r"#(\w+)")
_ZERO_WIDTH_RE = re.compile("[\u200b\u200c\u200d\ufeff]")
_REPEAT_RE = regex.compile(r"(\X)\1{3,}")
_WHITESPACE_RE = re.compile(r"\s+")

_HOMOGLYPHS = hg.Homoglyphs(
    categories=("LATIN", "CYRILLIC", "GREEK", "COMMON"),
    strategy=hg.STRATEGY_LOAD,
)


def _fold_homoglyphs(text: str) -> str:
    """Confusable non-Latin lookalikes -> their Latin/ASCII skeleton.
    """
    out = []
    for ch in text:
        if ch.isascii() or not ch.isalpha():
            out.append(ch)
            continue
        candidates = sorted(
            c for c in _HOMOGLYPHS.get_combinations(ch) if c.isascii() and c.isalpha()
        )
        out.append(candidates[0] if candidates else ch)
    return "".join(out)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _fold_homoglyphs(text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _REPEAT_RE.sub(r"\1\1\1", text)
    text = _URL_RE.sub("", text)
    text = _MENTION_RE.sub("", text)
    text = _HASHTAG_RE.sub(r"\1", text)
    return _WHITESPACE_RE.sub(" ", text).strip()

"""Dominant Unicode script detection.
"""

from collections import Counter

_CJK_RANGES = (
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
    (0x31F0, 0x31FF),  # Katakana phonetic extensions
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
    (0xAC00, 0xD7A3),  # Hangul syllables
    (0xFF00, 0xFFEF),  # Halfwidth and fullwidth forms
)
_CYRILLIC_RANGE = (0x0400, 0x04FF)
_GREEK_RANGE = (0x0370, 0x03FF)
_LATIN_RANGES = (
    (0x0041, 0x024F),  # ASCII + Latin-1 Supplement + Latin Extended-A/B
)


def _in_ranges(codepoint: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= codepoint <= hi for lo, hi in ranges)


def _bucket(ch: str) -> str | None:
    codepoint = ord(ch)
    if _in_ranges(codepoint, _CJK_RANGES):
        return "cjk"
    if _in_ranges(codepoint, (_CYRILLIC_RANGE,)):
        return "cyrillic"
    if _in_ranges(codepoint, (_GREEK_RANGE,)):
        return "greek"
    if _in_ranges(codepoint, _LATIN_RANGES):
        return "latin"
    return None


def detect_dominant_script(text: str) -> str:
    """Returns the most frequent Unicode script bucket among text's
    alphabetic characters: 'latin', 'cyrillic', 'greek', 'cjk', or 'other'.
    """
    counts: Counter[str] = Counter()
    for ch in text:
        if not ch.isalpha():
            continue
        bucket = _bucket(ch)
        counts[bucket or "other"] += 1

    if not counts:
        return "other"
    return counts.most_common(1)[0][0]

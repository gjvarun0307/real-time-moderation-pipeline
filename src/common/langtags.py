"""Language tag canonicalization.
"""

import pycountry


def canonicalize_lang(tag: str) -> str:
    primary = tag.split("-")[0].strip().lower()
    if not primary:
        return primary

    lang = pycountry.languages.get(alpha_2=primary) or pycountry.languages.get(alpha_3=primary)
    if lang is None:
        return primary

    alpha_2 = getattr(lang, "alpha_2", None)
    if alpha_2 is not None:
        return str(alpha_2)
    return str(lang.alpha_3)


def canonicalize_langs(tags: list[str] | None) -> list[str]:
    """Canonicalize a declared `langs` list, deduping while preserving first-seen order"""
    if not tags:
        return []
    seen: dict[str, None] = {}
    for tag in tags:
        canonical = canonicalize_lang(tag)
        if canonical:
            seen.setdefault(canonical, None)
    return list(seen)

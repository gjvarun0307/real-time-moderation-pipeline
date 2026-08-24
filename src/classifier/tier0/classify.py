"""Script-aware Tier 0 heuristic pass: HARD_ALLOW / HARD_BLOCK / PASS_TO_TIER1.
"""

from dataclasses import dataclass
from typing import Literal

import emoji

from classifier.tier0.lexicon import Lexicon
from classifier.tier0.script import detect_dominant_script
from common.schemas import PostsRawMessage

TIER0_MODEL_VERSION = "tier0-lexicon-v1"
UNIVERSAL_SHORT_ALLOW_MAX_CHARS = 2


@dataclass(frozen=True)
class Tier0Result:
    decision: Literal["HARD_ALLOW", "HARD_BLOCK", "PASS_TO_TIER1"]
    script: str
    matched_entry_id: str | None


def _is_trivially_benign(text: str) -> bool:
    """True if, once emoji are stripped, at most a couple of alphabetic
    characters remain — pure emoji/punctuation/whitespace posts."""
    remaining = emoji.replace_emoji(text, replace="")
    alpha_chars = [ch for ch in remaining if ch.isalpha()]
    return len(alpha_chars) <= UNIVERSAL_SHORT_ALLOW_MAX_CHARS


def classify(message: PostsRawMessage, lexicons: dict[str, Lexicon]) -> Tier0Result:
    """Runs the Tier 0 cascade over one message's normalized text."""
    text = message.text_normalized.casefold()
    script = detect_dominant_script(message.text_normalized)
    lexicon = lexicons.get(message.lang_predicted)

    if lexicon is not None:
        block_id = lexicon.matches(text, "hard_block")
        if block_id is not None:
            return Tier0Result(decision="HARD_BLOCK", script=script, matched_entry_id=block_id)

    if _is_trivially_benign(text):
        return Tier0Result(decision="HARD_ALLOW", script=script, matched_entry_id=None)

    if lexicon is not None:
        allow_id = lexicon.matches(text, "hard_allow")
        if allow_id is not None:
            return Tier0Result(decision="HARD_ALLOW", script=script, matched_entry_id=allow_id)

    return Tier0Result(decision="PASS_TO_TIER1", script=script, matched_entry_id=None)

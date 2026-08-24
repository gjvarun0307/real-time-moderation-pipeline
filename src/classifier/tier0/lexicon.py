"""Loading and matching Tier 0's per-language lexicon YAML files.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import structlog
import yaml

logger = structlog.get_logger()

_PLACEHOLDER_PREFIX = "<populate"


@dataclass(frozen=True)
class LexiconEntry:
    id: str
    term: str
    type: Literal["hard_allow", "hard_block"]
    notes: str


@dataclass(frozen=True)
class Lexicon:
    lang: str
    match_mode: Literal["word", "substring"]
    entries: list[LexiconEntry]

    def matches(
        self, text_casefolded: str, entry_type: Literal["hard_allow", "hard_block"]
    ) -> str | None:
        """Returns the id of the first matching entry of entry_type, or None."""
        for entry in self.entries:
            if entry.type != entry_type:
                continue
            if self.match_mode == "substring":
                hit = entry.term in text_casefolded
            else:
                hit = re.search(rf"\b{re.escape(entry.term)}\b", text_casefolded) is not None
            if hit:
                return entry.id
        return None


def load_lexicon(path: Path) -> Lexicon:
    """Loads one lexicon YAML file, casefolding every entry's term.

    Entries still carrying a `<POPULATE: ...>` placeholder term (the
    template shipped in git) are skipped with a warning rather than
    loaded as a literal, permanently-unmatchable "block" term — that
    would silently look like real protection when there is none.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = []
    for entry in data["entries"]:
        term = entry["term"].casefold()
        if term.startswith(_PLACEHOLDER_PREFIX):
            logger.warning(
                "tier0_lexicon_placeholder_skipped", lang=data["lang"], entry_id=entry["id"]
            )
            continue
        entries.append(
            LexiconEntry(
                id=entry["id"], term=term, type=entry["type"], notes=entry.get("notes", "")
            )
        )
    return Lexicon(lang=data["lang"], match_mode=data["match_mode"], entries=entries)


def load_lexicons(lexicon_dir: Path) -> dict[str, Lexicon]:
    """Loads every *.yaml file in lexicon_dir, keyed by each file's own `lang` field."""
    lexicons = {}
    for path in sorted(lexicon_dir.glob("*.yaml")):
        lexicon = load_lexicon(path)
        lexicons[lexicon.lang] = lexicon
    return lexicons

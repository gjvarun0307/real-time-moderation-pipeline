"""Self-consistency checks against the real, gitignored lexicon overrides
in models/lexicons.local/ — skipped where that directory doesn't exist
(fresh clones, CI) since it's never committed. No real term appears as a
literal in this file; every check is generic over whatever's loaded.
"""

from pathlib import Path

import pytest

from classifier.tier0.lexicon import load_lexicons

_LOCAL_LEXICON_DIR = Path(__file__).resolve().parents[2] / "models" / "lexicons.local"

pytestmark = pytest.mark.skipif(
    not _LOCAL_LEXICON_DIR.exists(), reason="models/lexicons.local/ not populated on this machine"
)


def _lexicons():
    return load_lexicons(_LOCAL_LEXICON_DIR)


def test_no_entries_are_still_placeholders():
    for lexicon in _lexicons().values():
        for entry in lexicon.entries:
            assert not entry.term.startswith("<populate"), (
                f"{entry.id} in {lexicon.lang}.yaml is still a placeholder"
            )


def test_every_hard_block_entry_matches_text_containing_only_itself():
    for lexicon in _lexicons().values():
        for entry in lexicon.entries:
            if entry.type != "hard_block":
                continue
            assert lexicon.matches(entry.term, "hard_block") == entry.id


def test_every_hard_allow_entry_matches_text_containing_only_itself():
    for lexicon in _lexicons().values():
        for entry in lexicon.entries:
            if entry.type != "hard_allow":
                continue
            assert lexicon.matches(entry.term, "hard_allow") == entry.id


def test_ids_are_unique_within_each_lexicon():
    for lexicon in _lexicons().values():
        ids = [entry.id for entry in lexicon.entries]
        assert len(ids) == len(set(ids))

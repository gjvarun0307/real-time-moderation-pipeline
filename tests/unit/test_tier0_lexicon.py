from pathlib import Path

from classifier.tier0.lexicon import load_lexicon, load_lexicons

_EN_YAML = """
lang: en
match_mode: word
entries:
  - id: en-allow-001
    term: "good morning"
    type: hard_allow
    notes: "common greeting"
  - id: en-block-001
    term: "badword"
    type: hard_block
    notes: "test slur placeholder"
"""

_JA_YAML = """
lang: ja
match_mode: substring
entries:
  - id: ja-allow-001
    term: "おはよう"
    type: hard_allow
    notes: "common greeting"
"""


def test_load_lexicon_casefolds_terms(tmp_path: Path):
    path = tmp_path / "en.yaml"
    path.write_text(_EN_YAML, encoding="utf-8")

    lexicon = load_lexicon(path)

    assert lexicon.lang == "en"
    assert lexicon.match_mode == "word"
    assert {e.term for e in lexicon.entries} == {"good morning", "badword"}


def test_word_mode_matches_on_word_boundaries(tmp_path: Path):
    path = tmp_path / "en.yaml"
    path.write_text(_EN_YAML, encoding="utf-8")
    lexicon = load_lexicon(path)

    assert lexicon.matches("say good morning to everyone", "hard_allow") == "en-allow-001"
    assert lexicon.matches("goodness morning glory", "hard_allow") is None
    assert lexicon.matches("that is a badword right there", "hard_block") == "en-block-001"
    assert lexicon.matches("badwording is not a real word", "hard_block") is None


def test_word_mode_is_case_insensitive_against_casefolded_input(tmp_path: Path):
    path = tmp_path / "en.yaml"
    path.write_text(_EN_YAML, encoding="utf-8")
    lexicon = load_lexicon(path)

    assert lexicon.matches("GOOD MORNING".casefold(), "hard_allow") == "en-allow-001"


def test_substring_mode_matches_inside_words(tmp_path: Path):
    path = tmp_path / "ja.yaml"
    path.write_text(_JA_YAML, encoding="utf-8")
    lexicon = load_lexicon(path)

    assert lexicon.matches("今日はおはようございます", "hard_allow") == "ja-allow-001"
    assert lexicon.matches("こんにちは", "hard_allow") is None


def test_placeholder_terms_are_skipped_not_loaded_as_literal_block_terms(tmp_path: Path):
    yaml_text = """
lang: en
match_mode: word
entries:
  - id: en-block-999
    term: "<POPULATE: unambiguous severe slur, category=racial>"
    type: hard_block
    notes: "placeholder"
  - id: en-allow-999
    term: "hello"
    type: hard_allow
    notes: "real entry"
"""
    path = tmp_path / "en.yaml"
    path.write_text(yaml_text, encoding="utf-8")

    lexicon = load_lexicon(path)

    assert [e.id for e in lexicon.entries] == ["en-allow-999"]
    assert lexicon.matches("well hello there", "hard_block") is None


def test_load_lexicons_keys_by_lang_field(tmp_path: Path):
    (tmp_path / "en.yaml").write_text(_EN_YAML, encoding="utf-8")
    (tmp_path / "ja.yaml").write_text(_JA_YAML, encoding="utf-8")

    lexicons = load_lexicons(tmp_path)

    assert set(lexicons) == {"en", "ja"}
    assert lexicons["en"].match_mode == "word"
    assert lexicons["ja"].match_mode == "substring"

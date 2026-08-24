from classifier.tier0.classify import classify
from classifier.tier0.lexicon import Lexicon, LexiconEntry
from common.schemas import PostsRawMessage

_EN_LEXICON = Lexicon(
    lang="en",
    match_mode="word",
    entries=[
        LexiconEntry(id="en-allow-001", term="good morning", type="hard_allow", notes=""),
        LexiconEntry(id="en-block-001", term="badword", type="hard_block", notes=""),
    ],
)


def _message(text: str, text_normalized: str | None = None, lang_predicted: str = "en"):
    return PostsRawMessage(
        id="01a01982-4c32-7782-9857-43f3fff3a7ec",
        post_uri="at://did:plc:abc/app.bsky.feed.post/xyz",
        author_hash="a" * 32,
        text=text,
        text_normalized=text_normalized if text_normalized is not None else text,
        lang_declared=lang_predicted,
        lang_declared_raw=lang_predicted,
        lang_predicted=lang_predicted,
        lang_confidence=0.9,
        event_time_us=1_000_000,
        ingest_time_us=1_000_100,
        char_len=len(text),
        has_emoji=False,
        source="live",
    )


def test_hard_block_takes_precedence_over_universal_allow():
    # short text that would otherwise look trivially benign, but contains
    # the block term — block must win.
    message = _message("badword")
    result = classify(message, {"en": _EN_LEXICON})
    assert result.decision == "HARD_BLOCK"
    assert result.matched_entry_id == "en-block-001"


def test_pure_emoji_is_hard_allow():
    message = _message("🎉🎉🎉")
    result = classify(message, {})
    assert result.decision == "HARD_ALLOW"
    assert result.matched_entry_id is None


def test_short_text_is_hard_allow():
    message = _message("ok")
    result = classify(message, {})
    assert result.decision == "HARD_ALLOW"


def test_lexicon_hard_allow_entry_hit():
    message = _message("say good morning to everyone today please")
    result = classify(message, {"en": _EN_LEXICON})
    assert result.decision == "HARD_ALLOW"
    assert result.matched_entry_id == "en-allow-001"


def test_no_lexicon_for_lang_passes_to_tier1():
    message = _message("some longer message with no special content here", lang_predicted="fr")
    result = classify(message, {"en": _EN_LEXICON})
    assert result.decision == "PASS_TO_TIER1"
    assert result.matched_entry_id is None


def test_ordinary_longer_text_passes_to_tier1():
    message = _message("this is just an ordinary longer post about something")
    result = classify(message, {"en": _EN_LEXICON})
    assert result.decision == "PASS_TO_TIER1"


def test_result_always_includes_a_script():
    message = _message("おはようございます", lang_predicted="ja")
    result = classify(message, {})
    assert result.script == "cjk"
    assert result.decision in ("HARD_ALLOW", "HARD_BLOCK", "PASS_TO_TIER1")

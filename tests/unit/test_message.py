from common.schemas import Commit, PostRecord, RawEvent
from ingest.filter import Accepted
from ingest.message import build_message, hash_author


def _accepted(text: str = "hello world", langs: list[str] | None = None) -> Accepted:
    commit = Commit(
        rev="abc",
        operation="create",
        collection="app.bsky.feed.post",
        rkey="xyz789",
        cid="bafy...",
        record=PostRecord(text=text, langs=langs),
    )
    return Accepted(commit=commit, post=commit.record)


def _event() -> RawEvent:
    return RawEvent(did="did:plc:abc123", time_us=1725911162329308, kind="commit")


def test_hash_author_is_deterministic_and_truncated():
    h1 = hash_author("did:plc:abc123", "salt-value")
    h2 = hash_author("did:plc:abc123", "salt-value")
    assert h1 == h2
    assert len(h1) == 32


def test_hash_author_differs_with_salt():
    h1 = hash_author("did:plc:abc123", "salt-a")
    h2 = hash_author("did:plc:abc123", "salt-b")
    assert h1 != h2


def test_hash_author_never_contains_raw_did():
    h = hash_author("did:plc:abc123", "salt-value")
    assert "did:plc:abc123" not in h


def test_build_message_post_uri_matches_dedup_key_format():
    msg = build_message(
        event=_event(),
        accepted=_accepted(),
        text_normalized="hello world",
        lang_declared="en",
        lang_declared_raw="en-US",
        lang_predicted="en",
        lang_confidence=0.97,
        salt="test-salt",
    )
    assert msg.post_uri == "at://did:plc:abc123/app.bsky.feed.post/xyz789"


def test_build_message_fields_map_correctly():
    msg = build_message(
        event=_event(),
        accepted=_accepted(text="Hello 😀 world"),
        text_normalized="hello world",
        lang_declared="en",
        lang_declared_raw="en-US",
        lang_predicted="en",
        lang_confidence=0.97,
        salt="test-salt",
    )
    assert msg.text == "Hello 😀 world"
    assert msg.text_normalized == "hello world"
    assert msg.char_len == len("Hello 😀 world")
    assert msg.has_emoji is True
    assert msg.event_time_us == 1725911162329308
    assert msg.source == "live"
    assert msg.schema_version == 2
    assert msg.author_hash == hash_author("did:plc:abc123", "test-salt")


def test_build_message_no_emoji_flagged_false():
    msg = build_message(
        event=_event(),
        accepted=_accepted(text="plain text, no emoji here"),
        text_normalized="plain text, no emoji here",
        lang_declared=None,
        lang_declared_raw=None,
        lang_predicted="en",
        lang_confidence=0.6,
        salt="test-salt",
    )
    assert msg.has_emoji is False


def test_build_message_missing_declared_lang_is_none():
    msg = build_message(
        event=_event(),
        accepted=_accepted(),
        text_normalized="hello world",
        lang_declared=None,
        lang_declared_raw=None,
        lang_predicted="en",
        lang_confidence=0.9,
        salt="test-salt",
    )
    assert msg.lang_declared is None
    assert msg.lang_declared_raw is None


def test_build_message_ids_are_unique_uuid7s():
    msg1 = build_message(
        event=_event(),
        accepted=_accepted(),
        text_normalized="hello world",
        lang_declared="en",
        lang_declared_raw="en",
        lang_predicted="en",
        lang_confidence=0.9,
        salt="test-salt",
    )
    msg2 = build_message(
        event=_event(),
        accepted=_accepted(),
        text_normalized="hello world",
        lang_declared="en",
        lang_declared_raw="en",
        lang_predicted="en",
        lang_confidence=0.9,
        salt="test-salt",
    )
    assert msg1.id != msg2.id

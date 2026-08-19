import time

from common.metrics import ingest_duplicates_total
from ingest.dedup import BloomDedup, build_post_key


def test_build_post_key_format():
    key = build_post_key("did:plc:abc123", "app.bsky.feed.post", "xyz789")
    assert key == "at://did:plc:abc123/app.bsky.feed.post/xyz789"


def test_first_seen_key_is_not_a_duplicate():
    dedup = BloomDedup()
    assert dedup.is_duplicate("at://did:plc:a/app.bsky.feed.post/1") is False


def test_repeated_key_is_flagged_as_duplicate():
    dedup = BloomDedup()
    key = "at://did:plc:a/app.bsky.feed.post/1"
    dedup.is_duplicate(key)
    assert dedup.is_duplicate(key) is True


def test_distinct_keys_do_not_collide():
    dedup = BloomDedup()
    assert dedup.is_duplicate("at://did:plc:a/app.bsky.feed.post/1") is False
    assert dedup.is_duplicate("at://did:plc:b/app.bsky.feed.post/2") is False


def test_duplicate_increments_metric():
    dedup = BloomDedup()
    key = "at://did:plc:a/app.bsky.feed.post/metric-test"
    before = ingest_duplicates_total._value.get()
    dedup.is_duplicate(key)
    dedup.is_duplicate(key)
    assert ingest_duplicates_total._value.get() == before + 1


def test_key_survives_one_rotation():
    # a key seen just before rotation should still be caught in the
    # newly-rotated window (it lives on in the "previous" filter)
    dedup = BloomDedup(window_seconds=0.05)
    key = "at://did:plc:a/app.bsky.feed.post/rotate-once"
    dedup.is_duplicate(key)
    time.sleep(0.06)
    assert dedup.is_duplicate(key) is True


def test_key_ages_out_after_two_rotations():
    dedup = BloomDedup(window_seconds=0.05)
    key = "at://did:plc:a/app.bsky.feed.post/rotate-twice"
    dedup.is_duplicate(key)
    time.sleep(0.06)
    dedup.is_duplicate("at://did:plc:b/app.bsky.feed.post/other")  # triggers rotation check
    time.sleep(0.06)
    assert dedup.is_duplicate(key) is False

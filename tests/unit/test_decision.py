from classifier.decision import MODEL_VERSION, decide_stub
from common.schemas import PostsRawMessage


def _message(event_time_us: int = 1_000_000) -> PostsRawMessage:
    return PostsRawMessage(
        id="01a01982-4c32-7782-9857-43f3fff3a7ec",
        post_uri="at://did:plc:abc/app.bsky.feed.post/xyz",
        author_hash="a" * 32,
        text="hello",
        text_normalized="hello",
        lang_declared="en",
        lang_declared_raw="en-US",
        lang_predicted="en",
        lang_confidence=0.9,
        event_time_us=event_time_us,
        ingest_time_us=event_time_us + 100,
        char_len=5,
        has_emoji=False,
        source="live",
    )


def test_decision_is_one_of_the_three_valid_values():
    for _ in range(200):
        verdict = decide_stub(_message())
        assert verdict.decision in ("ALLOW", "BLOCK", "REVIEW")


def test_decision_mix_is_weighted_toward_allow():
    # coarse sanity check on the 85/10/5 split, not a rigorous stats test
    counts = {"ALLOW": 0, "BLOCK": 0, "REVIEW": 0}
    for _ in range(5_000):
        counts[decide_stub(_message()).decision] += 1
    assert counts["ALLOW"] > counts["REVIEW"] > counts["BLOCK"]
    assert counts["ALLOW"] / 5_000 > 0.7


def test_carries_through_fields_from_the_source_message():
    message = _message()
    verdict = decide_stub(message)
    assert verdict.post_uri == message.post_uri
    assert verdict.author_hash == message.author_hash
    assert verdict.lang_predicted == message.lang_predicted
    assert verdict.lang_declared == message.lang_declared
    assert verdict.source == message.source
    assert verdict.event_time_us == message.event_time_us


def test_resolved_tier_and_model_version_mark_this_as_a_stub():
    verdict = decide_stub(_message())
    assert verdict.resolved_tier == 0
    assert verdict.model_version == MODEL_VERSION
    assert verdict.low_confidence is False
    assert verdict.escalation_sampled_out is False


def test_no_scores_since_no_real_model_exists_yet():
    verdict = decide_stub(_message())
    assert verdict.score_toxic is None
    assert verdict.score_severe is None


def test_latency_is_never_negative_even_for_a_future_event_time():
    import time

    future_us = int(time.time() * 1_000_000) + 60_000_000
    verdict = decide_stub(_message(event_time_us=future_us))
    assert verdict.latency_ms == 0

# VerdictStore itself isn't unit-tested here — it talks to a real
# Postgres connection pool via asyncpg, and there's no live database
# reachable from this machine (same class of limitation as the
# ingest-service Kafka producer before it was deployed). persist_reason()
# is pure and carries the actual selective-persistence decision logic
# from spec §6, so that's what's covered.

from classifier.persistence import persist_reason
from common.schemas import Verdict


def _verdict(**overrides: object) -> Verdict:
    defaults: dict[str, object] = {
        "id": "01a01982-4c32-7782-9857-43f3fff3a7ec",
        "post_uri": "at://did:plc:abc/app.bsky.feed.post/xyz",
        "author_hash": "a" * 32,
        "lang_predicted": "en",
        "lang_declared": "en",
        "lang_confidence": 0.9,
        "decision": "ALLOW",
        "resolved_tier": 0,
        "model_version": "stub-random-v0",
        "source": "live",
        "event_time_us": 1,
        "decided_time_us": 2,
        "latency_ms": 0,
    }
    defaults.update(overrides)
    return Verdict.model_validate(defaults)


def test_block_is_always_persisted():
    verdict = _verdict(decision="BLOCK")
    assert persist_reason(verdict, allow_sample_bps=0) == "block"


def test_review_is_always_persisted():
    verdict = _verdict(decision="REVIEW")
    assert persist_reason(verdict, allow_sample_bps=0) == "block"


def test_tier2_is_always_persisted_even_if_allow():
    verdict = _verdict(decision="ALLOW", resolved_tier=2)
    assert persist_reason(verdict, allow_sample_bps=0) == "tier2"


def test_low_confidence_is_always_persisted_even_if_allow():
    verdict = _verdict(decision="ALLOW", low_confidence=True)
    assert persist_reason(verdict, allow_sample_bps=0) == "low_conf"


def test_allow_is_persisted_when_sample_bps_is_maxed_out():
    verdict = _verdict(decision="ALLOW")
    assert persist_reason(verdict, allow_sample_bps=10_000) == "sample"


def test_allow_is_never_persisted_when_sample_bps_is_zero():
    verdict = _verdict(decision="ALLOW")
    assert persist_reason(verdict, allow_sample_bps=0) is None


def test_same_post_uri_always_takes_the_same_sampling_path():
    verdict = _verdict(decision="ALLOW", post_uri="at://did:plc:stable/app.bsky.feed.post/1")
    first = persist_reason(verdict, allow_sample_bps=5_000)
    second = persist_reason(verdict, allow_sample_bps=5_000)
    assert first == second

from common.determinism import deterministic_fraction
from common.metrics import ingest_dropped_total, ingest_queue_depth, ingest_sample_rate
from ingest.backpressure import AdaptiveQueue, sample_tier


def _find_key_below(rate: float, start: int = 0) -> str:
    i = start
    while True:
        key = f"probe-{i}"
        if deterministic_fraction(key) < rate:
            return key
        i += 1


def _find_key_at_least(rate: float, start: int = 0) -> str:
    i = start
    while True:
        key = f"probe-{i}"
        if deterministic_fraction(key) >= rate:
            return key
        i += 1


def test_sample_tier_boundaries():
    assert sample_tier(0.0) == ("NORMAL", 1.00)
    assert sample_tier(0.699) == ("NORMAL", 1.00)
    assert sample_tier(0.70) == ("DEGRADED", 0.50)
    assert sample_tier(0.849) == ("DEGRADED", 0.50)
    assert sample_tier(0.85) == ("HEAVY", 0.20)
    assert sample_tier(0.949) == ("HEAVY", 0.20)
    assert sample_tier(0.95) == ("CRITICAL", 0.05)
    assert sample_tier(1.0) == ("CRITICAL", 0.05)


def test_everything_admitted_at_normal_utilization():
    q: AdaptiveQueue[str] = AdaptiveQueue(maxsize=1000)
    for i in range(600):  # utilization stays well under 0.70
        assert q.offer(f"key-{i}", f"item-{i}") is True
    assert q.queue.qsize() == 600


def test_same_key_gets_same_decision_at_a_fixed_tier():
    # utilization pinned by a large maxsize relative to a handful of
    # offers, so the tier doesn't shift mid-test
    q1: AdaptiveQueue[str] = AdaptiveQueue(maxsize=1000)
    q2: AdaptiveQueue[str] = AdaptiveQueue(maxsize=1000)
    for i in range(50):
        assert q1.offer(f"key-{i}", "x") == q2.offer(f"key-{i}", "x")


def test_sampling_drops_the_expected_fraction_at_heavy_utilization():
    maxsize = 1000
    q: AdaptiveQueue[str] = AdaptiveQueue(maxsize=maxsize)
    # pre-fill directly to pin utilization at 0.90 (HEAVY, rate=0.20)
    # without going through offer()'s own admission logic
    for i in range(900):
        q.queue.put_nowait(f"prefill-{i}")

    admitted = 0
    attempts = 2000
    for i in range(attempts):
        if q.offer(f"probe-{i}", f"probe-item-{i}"):
            admitted += 1

    # some admitted items push utilization past 0.95 mid-run and into
    # CRITICAL (rate 0.05), so the true admit rate sits between the two
    # tiers' rates, not pinned to exactly 0.20
    assert 0.03 < admitted / attempts < 0.25


def test_queue_full_is_tracked_separately_from_sampled_out():
    maxsize = 10
    q: AdaptiveQueue[str] = AdaptiveQueue(maxsize=maxsize)
    for i in range(maxsize):
        q.queue.put_nowait(f"prefill-{i}")
    assert q.queue.full()

    # a key that would be admitted by CRITICAL's 5% rate, but the queue
    # itself has no room left
    key = _find_key_below(0.05)
    before = ingest_dropped_total.labels(reason="queue_full")._value.get()
    result = q.offer(key, "should not fit")
    after = ingest_dropped_total.labels(reason="queue_full")._value.get()

    assert result is False
    assert after == before + 1


def test_tier_transition_updates_gauges():
    q: AdaptiveQueue[str] = AdaptiveQueue(maxsize=10)
    for i in range(8):  # utilization 0.8 -> DEGRADED, rate 0.50
        q.queue.put_nowait(f"prefill-{i}")

    # rate gauge is set on every call regardless of admit/drop — use a
    # key guaranteed to be dropped here so the queue state (and tier)
    # doesn't shift before the next assertion
    q.offer(_find_key_at_least(0.50), "guaranteed dropped, state unchanged")
    assert ingest_sample_rate._value.get() == 0.50

    # depth gauge only updates on a successful admit, so force one with
    # a key guaranteed to pass the 0.50 threshold
    admitted_key = _find_key_below(0.50)
    assert q.offer(admitted_key, "item") is True
    assert ingest_queue_depth._value.get() == q.queue.qsize()

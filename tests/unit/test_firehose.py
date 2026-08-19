from ingest.firehose import compute_backoff


def test_compute_backoff_stays_within_bounds():
    for attempt in range(10):
        delay = compute_backoff(attempt, base=1.0, cap=60.0)
        assert 0 <= delay <= 60.0


def test_compute_backoff_respects_cap_even_at_high_attempt_counts():
    delay = compute_backoff(attempt=20, base=1.0, cap=60.0)
    assert delay <= 60.0


def test_compute_backoff_first_attempt_bounded_by_base():
    # attempt=0 -> min(cap, base * 2**0) == base
    delay = compute_backoff(attempt=0, base=1.0, cap=60.0)
    assert 0 <= delay <= 1.0

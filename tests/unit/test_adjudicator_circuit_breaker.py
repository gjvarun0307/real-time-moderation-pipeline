from adjudicator.circuit_breaker import CircuitBreaker, CircuitState


def test_starts_closed_and_allows_requests():
    breaker = CircuitBreaker(failure_threshold=5, open_seconds=30.0)
    assert breaker.state == CircuitState.CLOSED
    assert breaker.allow_request(now=0.0) is True


def test_stays_closed_below_failure_threshold():
    breaker = CircuitBreaker(failure_threshold=5, open_seconds=30.0)
    for i in range(4):
        breaker.record_failure(now=float(i))
    assert breaker.state == CircuitState.CLOSED
    assert breaker.allow_request(now=4.0) is True


def test_opens_on_the_nth_consecutive_failure():
    breaker = CircuitBreaker(failure_threshold=5, open_seconds=30.0)
    for i in range(5):
        breaker.record_failure(now=float(i))
    assert breaker.state == CircuitState.OPEN
    assert breaker.allow_request(now=5.0) is False


def test_success_resets_the_failure_count():
    breaker = CircuitBreaker(failure_threshold=5, open_seconds=30.0)
    for i in range(4):
        breaker.record_failure(now=float(i))
    breaker.record_success()
    for i in range(4):
        breaker.record_failure(now=10.0 + i)
    assert breaker.state == CircuitState.CLOSED  # still below threshold, count was reset


def test_transitions_to_half_open_after_cooldown():
    breaker = CircuitBreaker(failure_threshold=5, open_seconds=30.0)
    for i in range(5):
        breaker.record_failure(now=float(i))
    assert breaker.allow_request(now=4.0 + 30.0) is True
    assert breaker.state == CircuitState.HALF_OPEN


def test_half_open_allows_only_one_probe_at_a_time():
    breaker = CircuitBreaker(failure_threshold=5, open_seconds=30.0)
    for i in range(5):
        breaker.record_failure(now=float(i))
    assert breaker.allow_request(now=34.0) is True  # the one probe
    assert breaker.allow_request(now=34.1) is False  # a second concurrent probe


def test_half_open_probe_success_closes_the_circuit():
    breaker = CircuitBreaker(failure_threshold=5, open_seconds=30.0)
    for i in range(5):
        breaker.record_failure(now=float(i))
    breaker.allow_request(now=34.0)
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.allow_request(now=34.1) is True


def test_half_open_probe_failure_reopens_with_a_fresh_timer():
    breaker = CircuitBreaker(failure_threshold=5, open_seconds=30.0)
    for i in range(5):
        breaker.record_failure(now=float(i))
    breaker.allow_request(now=34.0)
    breaker.record_failure(now=34.0)
    assert breaker.state == CircuitState.OPEN
    assert breaker.allow_request(now=34.1) is False  # cooldown restarted
    assert breaker.allow_request(now=34.0 + 30.0) is True

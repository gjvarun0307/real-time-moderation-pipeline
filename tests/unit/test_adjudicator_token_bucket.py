from adjudicator.token_bucket import TokenBucket


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def test_acquire_does_not_sleep_when_tokens_available(monkeypatch):
    called = False

    async def fake_sleep(_seconds):
        nonlocal called
        called = True

    monkeypatch.setattr("adjudicator.token_bucket.asyncio.sleep", fake_sleep)
    bucket = TokenBucket(capacity=10, refill_per_second=1.0)
    clock = FakeClock()

    await bucket.acquire(cost=1.0, clock=clock)

    assert called is False


async def test_acquire_debits_the_requested_cost(monkeypatch):
    async def fake_sleep(_seconds):
        pass

    monkeypatch.setattr("adjudicator.token_bucket.asyncio.sleep", fake_sleep)
    bucket = TokenBucket(capacity=10, refill_per_second=1.0)
    clock = FakeClock()

    await bucket.acquire(cost=3.0, clock=clock)
    await bucket.acquire(cost=1.0, clock=clock)

    assert bucket._tokens == 6.0


async def test_acquire_sleeps_for_the_shortfall_when_empty(monkeypatch):
    sleep_durations = []

    async def fake_sleep(seconds):
        sleep_durations.append(seconds)

    monkeypatch.setattr("adjudicator.token_bucket.asyncio.sleep", fake_sleep)
    bucket = TokenBucket(capacity=1, refill_per_second=2.0)  # 1 token every 0.5s
    clock = FakeClock()

    await bucket.acquire(cost=1.0, clock=clock)  # drains the bucket
    await bucket.acquire(cost=1.0, clock=clock)  # needs to wait

    assert sleep_durations == [0.5]


async def test_refill_never_exceeds_capacity(monkeypatch):
    async def fake_sleep(_seconds):
        pass

    monkeypatch.setattr("adjudicator.token_bucket.asyncio.sleep", fake_sleep)
    bucket = TokenBucket(capacity=5, refill_per_second=10.0)
    clock = FakeClock()

    await bucket.acquire(cost=1.0, clock=clock)  # tokens now 4
    clock.advance(100.0)  # would refill far past capacity
    await bucket.acquire(cost=1.0, clock=clock)

    assert bucket._tokens == 4.0  # capped at capacity (5) minus the 1 just debited

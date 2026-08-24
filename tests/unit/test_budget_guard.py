from datetime import UTC, datetime

from classifier.budget_guard import BudgetGuard

_NOW = datetime(2026, 8, 24, tzinfo=UTC)


class FakeBudgetCounter:
    def __init__(self, initial_count: int = 0) -> None:
        self.count = initial_count
        self.increment_calls = 0

    async def current_count(self, now) -> int:
        return self.count

    async def increment(self, now) -> int:
        self.increment_calls += 1
        self.count += 1
        return self.count


async def test_same_post_id_gives_the_same_outcome_every_time():
    counter = FakeBudgetCounter()
    guard = BudgetGuard(counter, sample_bps=10_000, daily_cap=1000)  # always in-sample

    first = await guard.decide("post-a", now=_NOW)
    counter2 = FakeBudgetCounter()
    guard2 = BudgetGuard(counter2, sample_bps=10_000, daily_cap=1000)
    second = await guard2.decide("post-a", now=_NOW)

    assert first.escalate == second.escalate is True


async def test_zero_bps_never_escalates():
    counter = FakeBudgetCounter()
    guard = BudgetGuard(counter, sample_bps=0, daily_cap=1000)

    decision = await guard.decide("any-post", now=_NOW)

    assert decision.escalate is False
    assert decision.budget_exhausted is False
    assert counter.increment_calls == 0


async def test_full_bps_always_escalates_and_increments():
    counter = FakeBudgetCounter()
    guard = BudgetGuard(counter, sample_bps=10_000, daily_cap=1000)

    decision = await guard.decide("any-post", now=_NOW)

    assert decision.escalate is True
    assert decision.budget_exhausted is False
    assert counter.increment_calls == 1


async def test_cap_exhausted_short_circuits_regardless_of_bps_roll():
    counter = FakeBudgetCounter(initial_count=1000)
    guard = BudgetGuard(counter, sample_bps=10_000, daily_cap=1000)  # bps would always escalate

    decision = await guard.decide("any-post", now=_NOW)

    assert decision.escalate is False
    assert decision.budget_exhausted is True
    assert counter.increment_calls == 0


async def test_sampled_out_posts_do_not_consume_quota():
    counter = FakeBudgetCounter()
    guard = BudgetGuard(counter, sample_bps=0, daily_cap=1000)

    await guard.decide("post-a", now=_NOW)
    await guard.decide("post-b", now=_NOW)

    assert counter.count == 0

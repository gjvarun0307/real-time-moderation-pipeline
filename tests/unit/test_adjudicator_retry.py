import pytest

from adjudicator.providers.base import (
    ProviderClientError,
    ProviderRateLimited,
    ProviderServerError,
)
from adjudicator.retry import call_with_retry


def _scripted(exceptions_then_result):
    """Returns (fn, calls) where fn raises each exception in order, then
    returns the final non-exception value on subsequent calls."""
    calls = {"count": 0}

    async def fn():
        calls["count"] += 1
        item = exceptions_then_result[calls["count"] - 1]
        if isinstance(item, Exception):
            raise item
        return item

    return fn, calls


def _recording_sleep(calls):
    async def fake_sleep(seconds):
        calls.append(seconds)

    return fake_sleep


async def test_succeeds_on_first_try_without_sleeping(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr("adjudicator.retry.asyncio.sleep", _recording_sleep(sleep_calls))

    async def fn():
        return "ok"

    result = await call_with_retry(fn, max_retries=2, base_delay=1.0, max_delay=10.0)

    assert result == "ok"
    assert sleep_calls == []


async def test_retries_on_server_error_then_succeeds(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr("adjudicator.retry.asyncio.sleep", _recording_sleep(sleep_calls))
    monkeypatch.setattr("adjudicator.retry.random.uniform", lambda a, b: 0.0)
    fn, calls = _scripted([ProviderServerError("boom"), "ok"])

    result = await call_with_retry(fn, max_retries=2, base_delay=1.0, max_delay=10.0)

    assert result == "ok"
    assert calls["count"] == 2
    assert len(sleep_calls) == 1


async def test_retries_on_rate_limited_then_succeeds(monkeypatch):
    monkeypatch.setattr("adjudicator.retry.asyncio.sleep", _recording_sleep([]))
    monkeypatch.setattr("adjudicator.retry.random.uniform", lambda a, b: 0.0)
    fn, calls = _scripted([ProviderRateLimited("429"), "ok"])

    result = await call_with_retry(fn, max_retries=2, base_delay=1.0, max_delay=10.0)

    assert result == "ok"
    assert calls["count"] == 2


async def test_client_error_is_never_retried(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr("adjudicator.retry.asyncio.sleep", _recording_sleep(sleep_calls))

    async def fn():
        raise ProviderClientError("bad request")

    with pytest.raises(ProviderClientError):
        await call_with_retry(fn, max_retries=2, base_delay=1.0, max_delay=10.0)

    assert sleep_calls == []


async def test_exhausts_retries_and_raises(monkeypatch):
    monkeypatch.setattr("adjudicator.retry.asyncio.sleep", _recording_sleep([]))
    monkeypatch.setattr("adjudicator.retry.random.uniform", lambda a, b: 0.0)

    async def fn():
        raise ProviderServerError("still failing")

    with pytest.raises(ProviderServerError):
        await call_with_retry(fn, max_retries=2, base_delay=1.0, max_delay=10.0)


async def test_backoff_delay_is_capped_at_max_delay(monkeypatch):
    captured_bounds: list[tuple[float, float]] = []

    def fake_uniform(a, b):
        captured_bounds.append((a, b))
        return 0.0

    monkeypatch.setattr("adjudicator.retry.asyncio.sleep", _recording_sleep([]))
    monkeypatch.setattr("adjudicator.retry.random.uniform", fake_uniform)
    fn, _calls = _scripted(
        [ProviderServerError("1"), ProviderServerError("2"), "ok"]
    )

    await call_with_retry(fn, max_retries=2, base_delay=100.0, max_delay=5.0)

    # base_delay*2**attempt would blow past max_delay quickly; every upper
    # bound passed to random.uniform must be clamped to max_delay.
    assert all(upper <= 5.0 for _lower, upper in captured_bounds)

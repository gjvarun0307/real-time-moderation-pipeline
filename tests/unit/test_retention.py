from datetime import UTC, datetime, timedelta

from classifier import retention as retention_module
from classifier.retention import run_retention
from common.config import RetentionSettings


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query, *args):
        self.calls.append((query, args))
        return "DELETE 1"

    async def close(self) -> None:
        self.closed = True


def _settings(**overrides) -> RetentionSettings:
    defaults = {"database_url": "postgresql://fake/db"}
    defaults.update(overrides)
    return RetentionSettings(**defaults)


async def test_runs_all_three_deletes_with_configured_intervals(monkeypatch):
    fake_conn = FakeConnection()

    async def fake_connect(url):
        assert url == "postgresql://fake/db"
        return fake_conn

    monkeypatch.setattr(retention_module.asyncpg, "connect", fake_connect)

    results = await run_retention(
        _settings(sample_retention_days=30, replay_retention_days=7, rollup_retention_days=90)
    )

    assert set(results) == {"old_samples_deleted", "old_replay_deleted", "old_rollups_deleted"}
    assert len(fake_conn.calls) == 3
    cutoffs = [args[0] for _query, args in fake_conn.calls]
    # bound as real datetime cutoffs computed in Python, not SQL-side
    # `now() - $1` arithmetic — that shape left $1's type ambiguous to
    # Postgres, which resolved it as timestamptz and made `now() - $1`
    # an interval, breaking `decided_time < interval` (see
    # CLAUDE.local.md's retention job incident).
    now = datetime.now(UTC)
    for query, _args in fake_conn.calls:
        assert "now()" not in query
        assert "::interval" not in query
    expected_days = [30, 7, 90]
    for cutoff, days in zip(cutoffs, expected_days, strict=True):
        assert isinstance(cutoff, datetime)
        assert abs((now - timedelta(days=days)) - cutoff) < timedelta(seconds=5)


async def test_closes_connection_even_if_a_statement_fails(monkeypatch):
    fake_conn = FakeConnection()

    async def failing_execute(query, *args):
        raise RuntimeError("boom")

    fake_conn.execute = failing_execute

    async def fake_connect(url):
        return fake_conn

    monkeypatch.setattr(retention_module.asyncpg, "connect", fake_connect)

    try:
        await run_retention(_settings())
    except RuntimeError:
        pass

    assert fake_conn.closed is True

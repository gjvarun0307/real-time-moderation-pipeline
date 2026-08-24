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
    intervals = [args[0] for _query, args in fake_conn.calls]
    assert intervals == ["30 days", "7 days", "90 days"]


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

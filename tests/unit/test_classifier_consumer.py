import pytest

from classifier import consumer as consumer_module
from classifier.consumer import PostsConsumer


class FakeRecord:
    def __init__(self, value: bytes) -> None:
        self.value = value


class FakeAIOKafkaConsumer:
    def __init__(self, *_topics, **_kwargs) -> None:
        self.started = False
        self.stopped = False
        self.commits = 0
        self.records: list[FakeRecord] = []
        self._assignment: set[str] = set()
        self._highwater: dict[str, int | None] = {}
        self._position: dict[str, int | None] = {}

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def __aiter__(self):
        async def gen():
            for record in self.records:
                yield record

        return gen()

    async def commit(self) -> None:
        self.commits += 1

    def assignment(self) -> set[str]:
        return self._assignment

    def highwater(self, tp: str) -> int | None:
        return self._highwater.get(tp)

    async def position(self, tp: str) -> int | None:
        return self._position.get(tp)


@pytest.fixture
async def consumer(monkeypatch) -> tuple[PostsConsumer, FakeAIOKafkaConsumer]:
    monkeypatch.setattr(consumer_module, "AIOKafkaConsumer", FakeAIOKafkaConsumer)
    c = PostsConsumer(bootstrap_servers="fake:9092", topic="posts.raw", group_id="classifier")
    await c.start()
    fake = c._consumer
    return c, fake


async def test_start_delegates_to_underlying_consumer(consumer):
    _c, fake = consumer
    assert fake.started is True


async def test_stop_delegates_to_underlying_consumer(consumer):
    c, fake = consumer
    await c.stop()
    assert fake.stopped is True


async def test_messages_yields_records_from_underlying_consumer(consumer):
    c, fake = consumer
    fake.records = [FakeRecord(b"one"), FakeRecord(b"two")]
    seen = [record.value async for record in c.messages()]
    assert seen == [b"one", b"two"]


async def test_commit_delegates_to_underlying_consumer(consumer):
    c, fake = consumer
    await c.commit()
    assert fake.commits == 1


async def test_current_lag_sums_across_assigned_partitions(consumer):
    c, fake = consumer
    fake._assignment = {"posts.raw-0", "posts.raw-1"}
    fake._highwater = {"posts.raw-0": 100, "posts.raw-1": 50}
    fake._position = {"posts.raw-0": 90, "posts.raw-1": 50}
    assert await c.current_lag() == 10


async def test_current_lag_ignores_partitions_missing_highwater_or_position(consumer):
    c, fake = consumer
    fake._assignment = {"posts.raw-0"}
    fake._highwater = {}  # unknown yet
    fake._position = {"posts.raw-0": 5}
    assert await c.current_lag() == 0


async def test_current_lag_before_start_is_zero():
    c = PostsConsumer(bootstrap_servers="fake:9092", topic="posts.raw", group_id="classifier")
    assert await c.current_lag() == 0

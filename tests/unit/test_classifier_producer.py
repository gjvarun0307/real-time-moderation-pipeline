import orjson
import pytest

from classifier import producer as producer_module
from classifier.producer import VerdictProducer
from common.schemas import Verdict


class FakeAIOKafkaProducer:
    def __init__(self, **_kwargs) -> None:
        self.started = False
        self.stopped = False
        self.sent: list[tuple[str, bytes | None, bytes | None]] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send_and_wait(self, topic, value=None, key=None):
        self.sent.append((topic, value, key))


@pytest.fixture
async def producer(monkeypatch) -> tuple[VerdictProducer, FakeAIOKafkaProducer]:
    monkeypatch.setattr(producer_module, "AIOKafkaProducer", FakeAIOKafkaProducer)
    p = VerdictProducer(bootstrap_servers="fake:9092", topic="moderation.verdicts")
    await p.start()
    fake = p._producer
    return p, fake


def _verdict() -> Verdict:
    return Verdict.model_validate(
        {
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
    )


async def test_start_delegates_to_underlying_producer(producer):
    _p, fake = producer
    assert fake.started is True


async def test_stop_delegates_to_underlying_producer(producer):
    p, fake = producer
    await p.stop()
    assert fake.stopped is True


async def test_produce_verdict_sends_to_the_verdicts_topic_keyed_by_author_hash(producer):
    p, fake = producer
    verdict = _verdict()
    await p.produce_verdict(verdict)

    assert len(fake.sent) == 1
    topic, value, key = fake.sent[0]
    assert topic == "moderation.verdicts"
    assert key == verdict.author_hash.encode("utf-8")
    assert orjson.loads(value) == verdict.model_dump()


async def test_produce_verdict_before_start_raises_clearly():
    p = VerdictProducer(bootstrap_servers="fake:9092", topic="moderation.verdicts")
    with pytest.raises(RuntimeError, match="start"):
        await p.produce_verdict(_verdict())

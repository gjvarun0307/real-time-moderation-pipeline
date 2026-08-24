import orjson
import pytest

from adjudicator import producer as producer_module
from adjudicator.producer import AdjudicatorProducer
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
async def producer(monkeypatch) -> tuple[AdjudicatorProducer, FakeAIOKafkaProducer]:
    monkeypatch.setattr(producer_module, "AIOKafkaProducer", FakeAIOKafkaProducer)
    p = AdjudicatorProducer(
        bootstrap_servers="fake:9092",
        verdicts_topic="moderation.verdicts",
        dlq_topic="moderation.dlq",
    )
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
            "decision": "BLOCK",
            "resolved_tier": 2,
            "model_version": "tier1-onnx-v1-abc",
            "prompt_version": "adjudicate_v1",
            "adjudicator_provider": "groq",
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
    p = AdjudicatorProducer(
        bootstrap_servers="fake:9092",
        verdicts_topic="moderation.verdicts",
        dlq_topic="moderation.dlq",
    )
    with pytest.raises(RuntimeError, match="start"):
        await p.produce_verdict(_verdict())


async def test_produce_dlq_sends_to_the_dlq_topic_with_reason(producer):
    p, fake = producer
    await p.produce_dlq("validation_failed_after_repair", {"provider": "groq"})

    assert len(fake.sent) == 1
    topic, value, _key = fake.sent[0]
    assert topic == "moderation.dlq"
    body = orjson.loads(value)
    assert body["reason"] == "validation_failed_after_repair"
    assert body["raw"] == {"provider": "groq"}
    assert "dlq_time_us" in body


async def test_produce_dlq_falls_back_to_string_for_unserializable_payload(producer):
    p, fake = producer

    class Unserializable:
        pass

    await p.produce_dlq("weird_error", Unserializable())

    _topic, value, _key = fake.sent[0]
    body = orjson.loads(value)
    assert "Unserializable" in body["raw"]


async def test_produce_dlq_before_start_raises_clearly():
    p = AdjudicatorProducer(
        bootstrap_servers="fake:9092",
        verdicts_topic="moderation.verdicts",
        dlq_topic="moderation.dlq",
    )
    with pytest.raises(RuntimeError, match="start"):
        await p.produce_dlq("reason", {})

import orjson
import pytest

from common.schemas import PostsRawMessage
from ingest import producer as producer_module
from ingest.producer import PostsProducer


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
async def producer(monkeypatch) -> tuple[PostsProducer, FakeAIOKafkaProducer]:
    # substitutes the real Kafka client for a fake one so start() exercises
    # the real code path without an actual network connection
    monkeypatch.setattr(producer_module, "AIOKafkaProducer", FakeAIOKafkaProducer)
    p = PostsProducer(bootstrap_servers="fake:9092", topic="posts.raw", dlq_topic="moderation.dlq")
    await p.start()
    fake = p._producer
    return p, fake


def _message() -> PostsRawMessage:
    return PostsRawMessage(
        id="01a01982-4c32-7782-9857-43f3fff3a7ec",
        post_uri="at://did:plc:abc/app.bsky.feed.post/xyz",
        author_hash="a" * 32,
        text="hello",
        text_normalized="hello",
        lang_declared="en",
        lang_declared_raw="en-US",
        lang_predicted="en",
        lang_confidence=0.9,
        event_time_us=123,
        ingest_time_us=456,
        char_len=5,
        has_emoji=False,
        source="live",
    )


async def test_start_delegates_to_underlying_producer(producer):
    _p, fake = producer
    assert fake.started is True


async def test_stop_delegates_to_underlying_producer(producer):
    p, fake = producer
    await p.stop()
    assert fake.stopped is True


async def test_produce_post_sends_to_the_posts_topic_keyed_by_author_hash(producer):
    p, fake = producer
    msg = _message()
    await p.produce_post(msg)

    assert len(fake.sent) == 1
    topic, value, key = fake.sent[0]
    assert topic == "posts.raw"
    assert key == msg.author_hash.encode("utf-8")
    assert orjson.loads(value) == msg.model_dump()


async def test_produce_dlq_sends_to_the_dlq_topic_with_reason(producer):
    p, fake = producer
    await p.produce_dlq("schema_invalid", {"did": "did:plc:abc", "bad": True})

    assert len(fake.sent) == 1
    topic, value, key = fake.sent[0]
    assert topic == "moderation.dlq"
    body = orjson.loads(value)
    assert body["reason"] == "schema_invalid"
    assert body["raw"] == {"did": "did:plc:abc", "bad": True}
    assert "dlq_time_us" in body


async def test_produce_dlq_falls_back_to_string_for_unserializable_payload(producer):
    p, fake = producer

    class Unserializable:
        pass

    await p.produce_dlq("weird_error", Unserializable())

    _topic, value, _key = fake.sent[0]
    body = orjson.loads(value)
    assert "Unserializable" in body["raw"]


async def test_produce_post_before_start_raises_clearly():
    p = PostsProducer(bootstrap_servers="fake:9092", topic="posts.raw", dlq_topic="moderation.dlq")
    with pytest.raises(RuntimeError, match="start"):
        await p.produce_post(_message())

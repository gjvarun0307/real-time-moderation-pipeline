import asyncio
from collections.abc import AsyncIterator

import pytest

from common.config import IngestSettings
from common.schemas import PostsRawMessage, RawEvent
from ingest.backpressure import AdaptiveQueue
from ingest.dedup import BloomDedup
from ingest.firehose import FirehoseSource
from ingest.service import IngestService


class FakeFirehoseSource(FirehoseSource):
    def __init__(self, events: list[RawEvent]) -> None:
        self._events = events

    async def stream(self) -> AsyncIterator[RawEvent]:
        for event in self._events:
            yield event


class FakeIdentifier:
    def __init__(self, lang: str = "en", confidence: float = 0.9) -> None:
        self.lang = lang
        self.confidence = confidence

    def predict(self, _text: str) -> tuple[str, float]:
        return self.lang, self.confidence


class FakeCursorStore:
    async def close(self) -> None:
        pass


class FakeProducer:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.dlq_calls: list[tuple[str, object]] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def produce_post(self, message: PostsRawMessage) -> None:
        pass

    async def produce_dlq(self, reason: str, raw_payload: object) -> None:
        self.dlq_calls.append((reason, raw_payload))


def _settings() -> IngestSettings:
    return IngestSettings(author_hash_salt="test-salt")


def _valid_post_event(rkey: str = "xyz", text: str = "hello world") -> RawEvent:
    return RawEvent.model_validate(
        {
            "did": "did:plc:abc123",
            "time_us": 1000,
            "kind": "commit",
            "commit": {
                "rev": "r1",
                "operation": "create",
                "collection": "app.bsky.feed.post",
                "rkey": rkey,
                "cid": "bafy",
                "record": {"text": text, "langs": ["en"]},
            },
        }
    )


def _malformed_commit_event() -> RawEvent:
    return RawEvent.model_validate(
        {
            "did": "did:plc:bad",
            "time_us": 2000,
            "kind": "commit",
            "commit": {"operation": "create"},  # missing required fields
        }
    )


def _identity_event() -> RawEvent:
    return RawEvent.model_validate({"did": "did:plc:x", "time_us": 3000, "kind": "identity"})


def _build_service(
    events: list[RawEvent], identifier: FakeIdentifier | None = None
) -> tuple[IngestService, FakeProducer, "AdaptiveQueue[PostsRawMessage]"]:
    queue: AdaptiveQueue[PostsRawMessage] = AdaptiveQueue(maxsize=100)
    producer = FakeProducer()
    service = IngestService(
        settings=_settings(),
        source=FakeFirehoseSource(events),
        identifier=identifier or FakeIdentifier(),
        dedup=BloomDedup(),
        queue=queue,
        producer=producer,
        cursor_store=FakeCursorStore(),
    )
    return service, producer, queue


async def test_accepted_post_lands_in_queue():
    service, _producer, queue = _build_service([_valid_post_event()])
    await service.run_ingest_loop()
    assert queue.queue.qsize() == 1
    message = queue.queue.get_nowait()
    assert message.text == "hello world"
    assert message.lang_predicted == "en"


async def test_schema_invalid_event_goes_to_dlq_not_queue():
    service, producer, queue = _build_service([_malformed_commit_event()])
    await service.run_ingest_loop()
    assert queue.queue.qsize() == 0
    assert len(producer.dlq_calls) == 1
    assert producer.dlq_calls[0][0] == "schema_invalid"


async def test_non_dlq_rejection_is_silently_dropped():
    service, producer, queue = _build_service([_identity_event()])
    await service.run_ingest_loop()
    assert queue.queue.qsize() == 0
    assert len(producer.dlq_calls) == 0


async def test_duplicate_post_only_enqueued_once():
    event = _valid_post_event(rkey="same-rkey")
    service, _producer, queue = _build_service([event, event])
    await service.run_ingest_loop()
    assert queue.queue.qsize() == 1


async def test_one_bad_event_does_not_stop_the_loop(monkeypatch):
    import ingest.service as service_module

    calls = {"n": 0}
    real_normalize = service_module.normalize

    def flaky_normalize(text: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("simulated unexpected failure")
        return real_normalize(text)

    monkeypatch.setattr(service_module, "normalize", flaky_normalize)

    events = [_valid_post_event(rkey="first"), _valid_post_event(rkey="second")]
    service, _producer, queue = _build_service(events)
    await service.run_ingest_loop()

    # first event's handling raised and was swallowed; second still processed
    assert queue.queue.qsize() == 1
    assert queue.queue.get_nowait().post_uri.endswith("/second")


async def test_run_produce_loop_drains_queue_via_producer():
    queue: AdaptiveQueue[PostsRawMessage] = AdaptiveQueue(maxsize=10)
    producer = FakeProducer()
    sent: list[PostsRawMessage] = []

    async def capture(message: PostsRawMessage) -> None:
        sent.append(message)

    producer.produce_post = capture  # type: ignore[method-assign]

    service = IngestService(
        settings=_settings(),
        source=FakeFirehoseSource([]),
        identifier=FakeIdentifier(),
        dedup=BloomDedup(),
        queue=queue,
        producer=producer,
        cursor_store=FakeCursorStore(),
    )

    msg = PostsRawMessage(
        id="01a01982-4c32-7782-9857-43f3fff3a7ec",
        post_uri="at://did:plc:a/app.bsky.feed.post/1",
        author_hash="a" * 32,
        text="hi",
        text_normalized="hi",
        lang_declared="en",
        lang_declared_raw="en",
        lang_predicted="en",
        lang_confidence=0.9,
        event_time_us=1,
        ingest_time_us=2,
        char_len=2,
        has_emoji=False,
        source="live",
    )
    queue.queue.put_nowait(msg)

    task = asyncio.create_task(service.run_produce_loop())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert sent == [msg]

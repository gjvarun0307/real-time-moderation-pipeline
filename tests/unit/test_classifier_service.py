import time
from types import SimpleNamespace

import orjson

from classifier import service as service_module
from classifier.service import ClassifierService
from common.config import ClassifierSettings
from common.schemas import PostsRawMessage, Verdict


class FakeConsumer:
    def __init__(self, raw_values: list[bytes]) -> None:
        self._raw_values = raw_values
        self.commits = 0
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def messages(self):
        for value in self._raw_values:
            yield SimpleNamespace(value=value)

    async def commit(self) -> None:
        self.commits += 1

    async def current_lag(self) -> int:
        return 0


class FakeProducer:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.produced: list[Verdict] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def produce_verdict(self, verdict: Verdict) -> None:
        self.produced.append(verdict)


class FakeStore:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.inserted: list[tuple[Verdict, str]] = []
        self.rolled_up: list[Verdict] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def insert_verdict(self, verdict: Verdict, reason: str) -> None:
        self.inserted.append((verdict, reason))

    async def upsert_rollup(self, verdict: Verdict) -> None:
        self.rolled_up.append(verdict)


def _settings(allow_sample_bps: int = 0) -> ClassifierSettings:
    return ClassifierSettings(
        database_url="postgresql://fake/db", allow_sample_bps=allow_sample_bps
    )


def _post_bytes(post_uri: str = "at://did:plc:a/app.bsky.feed.post/1") -> bytes:
    message = PostsRawMessage(
        id="01a01982-4c32-7782-9857-43f3fff3a7ec",
        post_uri=post_uri,
        author_hash="a" * 32,
        text="hi",
        text_normalized="hi",
        lang_declared="en",
        lang_declared_raw="en",
        lang_predicted="en",
        lang_confidence=0.9,
        event_time_us=int(time.time() * 1_000_000),
        ingest_time_us=int(time.time() * 1_000_000),
        char_len=2,
        has_emoji=False,
        source="live",
    )
    return orjson.dumps(message.model_dump())


def _fixed_decision(decision: str):
    def decide(message: PostsRawMessage) -> Verdict:
        return Verdict(
            id="01a01982-4c32-7782-9857-43f3fff3a7ec",
            post_uri=message.post_uri,
            author_hash=message.author_hash,
            lang_predicted=message.lang_predicted,
            lang_declared=message.lang_declared,
            lang_confidence=message.lang_confidence,
            decision=decision,
            resolved_tier=0,
            model_version="stub-random-v0",
            source=message.source,
            event_time_us=message.event_time_us,
            decided_time_us=message.event_time_us + 1000,
            latency_ms=1,
        )

    return decide


def _build(raw_values: list[bytes], allow_sample_bps: int = 0):
    consumer = FakeConsumer(raw_values)
    producer = FakeProducer()
    store = FakeStore()
    service = ClassifierService(
        settings=_settings(allow_sample_bps),
        consumer=consumer,
        producer=producer,
        store=store,
    )
    return service, consumer, producer, store


async def test_block_decision_is_produced_and_persisted_as_a_full_row(monkeypatch):
    monkeypatch.setattr(service_module, "decide_stub", _fixed_decision("BLOCK"))
    service, consumer, producer, store = _build([_post_bytes()])

    await service.run_consume_loop()

    assert len(producer.produced) == 1
    assert producer.produced[0].decision == "BLOCK"
    assert len(store.inserted) == 1
    assert store.inserted[0][1] == "block"
    assert store.rolled_up == []
    assert consumer.commits == 1


async def test_allow_decision_with_zero_sample_rate_goes_to_rollup_only(monkeypatch):
    monkeypatch.setattr(service_module, "decide_stub", _fixed_decision("ALLOW"))
    service, consumer, producer, store = _build([_post_bytes()], allow_sample_bps=0)

    await service.run_consume_loop()

    assert len(producer.produced) == 1
    assert store.inserted == []
    assert len(store.rolled_up) == 1
    assert consumer.commits == 1


async def test_allow_decision_with_full_sample_rate_is_persisted(monkeypatch):
    monkeypatch.setattr(service_module, "decide_stub", _fixed_decision("ALLOW"))
    service, consumer, producer, store = _build([_post_bytes()], allow_sample_bps=10_000)

    await service.run_consume_loop()

    assert len(store.inserted) == 1
    assert store.inserted[0][1] == "sample"


async def test_malformed_record_is_skipped_without_committing_or_stopping_the_loop(monkeypatch):
    monkeypatch.setattr(service_module, "decide_stub", _fixed_decision("ALLOW"))
    service, consumer, producer, store = _build(
        [b"not valid json {{{", _post_bytes(post_uri="at://did:plc:b/app.bsky.feed.post/2")]
    )

    await service.run_consume_loop()

    # only the second, valid record was handled and committed
    assert len(producer.produced) == 1
    assert consumer.commits == 1


async def test_start_and_stop_wire_through_to_all_three_collaborators():
    service, consumer, producer, store = _build([])
    await service.start()
    assert service.is_ready() is True
    assert consumer.started and producer.started and store.started

    await service.stop()
    assert service.is_ready() is False
    assert consumer.stopped and producer.stopped and store.stopped

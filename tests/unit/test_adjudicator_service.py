from types import SimpleNamespace

import orjson

from adjudicator.client import AdjudicateOutcome
from adjudicator.service import AdjudicatorService
from common.config import AdjudicatorSettings
from common.schemas import AdjudicateResponse, EscalateMessage, Verdict


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
        self.dlq: list[tuple[str, object]] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def produce_verdict(self, verdict: Verdict) -> None:
        self.produced.append(verdict)

    async def produce_dlq(self, reason: str, raw_payload) -> None:
        self.dlq.append((reason, raw_payload))


class FakeOverflowFlag:
    def __init__(self) -> None:
        self.closed = False

    async def set_active(self) -> None:
        pass

    async def clear(self) -> None:
        pass

    async def close(self) -> None:
        self.closed = True


class FakeAdjudicatorClient:
    def __init__(self, outcome: AdjudicateOutcome) -> None:
        self._outcome = outcome
        self.calls: list[EscalateMessage] = []

    async def adjudicate(self, message: EscalateMessage) -> AdjudicateOutcome:
        self.calls.append(message)
        return self._outcome


def _settings() -> AdjudicatorSettings:
    return AdjudicatorSettings(groq_api_key="k", gemini_api_key="k")


def _escalate_bytes(post_uri: str = "at://did:plc:a/app.bsky.feed.post/1") -> bytes:
    message = EscalateMessage(
        id="01a01982-4c32-7782-9857-43f3fff3a7ec",
        post_uri=post_uri,
        author_hash="a" * 32,
        text="hi",
        text_normalized="hi",
        lang_predicted="en",
        lang_declared="en",
        lang_confidence=0.9,
        tier1_score_toxic=0.5,
        tier1_model_version="tier1-onnx-fake",
        source="live",
        event_time_us=1,
        escalated_time_us=2,
    )
    return orjson.dumps(message.model_dump())


def _build(raw_values: list[bytes], outcome: AdjudicateOutcome):
    consumer = FakeConsumer(raw_values)
    producer = FakeProducer()
    overflow_flag = FakeOverflowFlag()
    client = FakeAdjudicatorClient(outcome)
    service = AdjudicatorService(
        settings=_settings(),
        consumer=consumer,
        producer=producer,
        overflow_flag=overflow_flag,
        client=client,
    )
    return service, consumer, producer, overflow_flag, client


async def test_verdict_outcome_is_produced_and_committed():
    response = AdjudicateResponse(
        decision="BLOCK",
        score_toxic=0.9,
        score_severe=0.5,
        score_obscene=0.1,
        score_threat=0.7,
        score_insult=0.3,
        score_identity=0.1,
        rationale="explicit threat",
    )
    outcome = AdjudicateOutcome(kind="verdict", response=response, provider="groq")
    service, consumer, producer, _flag, _client = _build([_escalate_bytes()], outcome)

    await service.run_consume_loop()

    assert len(producer.produced) == 1
    assert producer.produced[0].decision == "BLOCK"
    assert producer.produced[0].resolved_tier == 2
    assert producer.dlq == []
    assert consumer.commits == 1


async def test_dlq_outcome_is_produced_and_skips_verdict():
    outcome = AdjudicateOutcome(
        kind="dlq", reason="all_providers_failed", context={"provider": None}
    )
    service, consumer, producer, _flag, _client = _build([_escalate_bytes()], outcome)

    await service.run_consume_loop()

    assert producer.produced == []
    assert len(producer.dlq) == 1
    assert producer.dlq[0][0] == "all_providers_failed"
    assert consumer.commits == 1


async def test_malformed_record_is_skipped_without_committing_or_stopping_the_loop():
    outcome = AdjudicateOutcome(kind="dlq", reason="unused")
    service, consumer, producer, _flag, client = _build(
        [b"not valid json {{{", _escalate_bytes(post_uri="at://did:plc:b/app.bsky.feed.post/2")],
        outcome,
    )

    await service.run_consume_loop()

    # only the second, valid record reached the client and got committed
    assert len(client.calls) == 1
    assert consumer.commits == 1


async def test_start_and_stop_wire_through_to_all_collaborators():
    outcome = AdjudicateOutcome(kind="dlq", reason="unused")
    service, consumer, producer, overflow_flag, _client = _build([], outcome)

    await service.start()
    assert service.is_ready() is True
    assert consumer.started and producer.started

    await service.stop()
    assert service.is_ready() is False
    assert consumer.stopped and producer.stopped
    assert overflow_flag.closed is True

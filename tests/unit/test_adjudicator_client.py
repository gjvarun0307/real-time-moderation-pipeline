import time
from pathlib import Path

from adjudicator.circuit_breaker import CircuitBreaker
from adjudicator.client import AdjudicatorClient
from adjudicator.prompt import PromptBuilder
from adjudicator.providers.base import (
    AdjudicationUsage,
    ProviderResult,
    ProviderServerError,
)
from adjudicator.token_bucket import TokenBucket
from common.config import AdjudicatorSettings
from common.schemas import EscalateMessage

_VALID_JSON = (
    '{"decision": "ALLOW", "score_toxic": 0.1, "score_severe": 0.1, '
    '"score_obscene": 0.1, "score_threat": 0.1, "score_insult": 0.1, '
    '"score_identity": 0.1, "rationale": "ok"}'
)


class FakeProvider:
    def __init__(self, name: str, results: list):
        self.name = name
        self._results = list(results)
        self.calls: list[str] = []

    async def complete(self, *, prompt: str, timeout: float) -> ProviderResult:
        self.calls.append(prompt)
        item = self._results.pop(0)
        if isinstance(item, Exception):
            raise item
        return ProviderResult(
            raw_text=item, usage=AdjudicationUsage(prompt_tokens=1, completion_tokens=1)
        )


def _settings(**overrides) -> AdjudicatorSettings:
    defaults = {
        "groq_api_key": "k",
        "gemini_api_key": "k",
        "retry_max": 0,
    }
    defaults.update(overrides)
    return AdjudicatorSettings(**defaults)


def _message() -> EscalateMessage:
    return EscalateMessage(
        id="01a01982-4c32-7782-9857-43f3fff3a7ec",
        post_uri="at://did:plc:abc/app.bsky.feed.post/xyz",
        author_hash="a" * 32,
        text="hello",
        text_normalized="hello",
        lang_predicted="en",
        lang_declared="en",
        lang_confidence=0.9,
        tier1_score_toxic=0.5,
        tier1_model_version="tier1-onnx-fake",
        source="live",
        event_time_us=1,
        escalated_time_us=2,
    )


def _prompt_builder(tmp_path: Path) -> PromptBuilder:
    template = tmp_path / "adjudicate_v1.txt"
    template.write_text("lang={lang} text={text} score={tier1_score_toxic}", encoding="utf-8")
    return PromptBuilder(template)


def _client(providers, tmp_path, **settings_overrides):
    breakers = {p.name: CircuitBreaker(failure_threshold=5, open_seconds=30.0) for p in providers}
    buckets = {p.name: TokenBucket(capacity=1000, refill_per_second=1000) for p in providers}
    return AdjudicatorClient(
        providers=providers,
        breakers=breakers,
        buckets=buckets,
        prompt_builder=_prompt_builder(tmp_path),
        settings=_settings(**settings_overrides),
    )


async def test_success_returns_verdict_outcome(tmp_path):
    groq = FakeProvider("groq", [_VALID_JSON])
    client = _client([groq], tmp_path)

    outcome = await client.adjudicate(_message())

    assert outcome.kind == "verdict"
    assert outcome.provider == "groq"
    assert outcome.response.decision == "ALLOW"


async def test_invalid_json_triggers_repair_then_succeeds(tmp_path):
    groq = FakeProvider("groq", ["not json", _VALID_JSON])
    client = _client([groq], tmp_path)

    outcome = await client.adjudicate(_message())

    assert outcome.kind == "verdict"
    assert len(groq.calls) == 2  # original + repair


async def test_invalid_json_twice_goes_to_dlq(tmp_path):
    groq = FakeProvider("groq", ["not json", "still not json"])
    client = _client([groq], tmp_path)

    outcome = await client.adjudicate(_message())

    assert outcome.kind == "dlq"
    assert outcome.reason == "validation_failed_after_repair"


async def test_failover_to_second_provider_on_server_error(tmp_path):
    groq = FakeProvider("groq", [ProviderServerError("down")])
    gemini = FakeProvider("gemini", [_VALID_JSON])
    client = _client([groq, gemini], tmp_path)

    outcome = await client.adjudicate(_message())

    assert outcome.kind == "verdict"
    assert outcome.provider == "gemini"


async def test_all_providers_exhausted_goes_to_dlq(tmp_path):
    groq = FakeProvider("groq", [ProviderServerError("down")])
    gemini = FakeProvider("gemini", [ProviderServerError("also down")])
    client = _client([groq, gemini], tmp_path)

    outcome = await client.adjudicate(_message())

    assert outcome.kind == "dlq"
    assert outcome.reason == "all_providers_failed"


async def test_open_circuit_skips_provider_without_calling_it(tmp_path):
    groq = FakeProvider("groq", [ProviderServerError("unused")])
    gemini = FakeProvider("gemini", [_VALID_JSON])

    breakers = {
        "groq": CircuitBreaker(failure_threshold=1, open_seconds=30.0),
        "gemini": CircuitBreaker(5, 30.0),
    }
    # real time.monotonic(), matching what the client itself calls internally —
    # a fake/zeroed timestamp here would make the real elapsed-time check in
    # allow_request() look like the cooldown already passed.
    breakers["groq"].record_failure(now=time.monotonic())  # trips it open after 1 failure
    buckets = {"groq": TokenBucket(1000, 1000), "gemini": TokenBucket(1000, 1000)}

    client = AdjudicatorClient(
        providers=[groq, gemini],
        breakers=breakers,
        buckets=buckets,
        prompt_builder=_prompt_builder(tmp_path),
        settings=_settings(),
    )

    outcome = await client.adjudicate(_message())

    assert outcome.kind == "verdict"
    assert outcome.provider == "gemini"
    assert groq.calls == []  # never called — breaker skipped it

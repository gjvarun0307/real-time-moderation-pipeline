from adjudicator.verdict_builder import build_verdict
from common.schemas import AdjudicateResponse, EscalateMessage


def _message(event_time_us: int = 1_000_000) -> EscalateMessage:
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
        tier1_model_version="tier1-onnx-v1-abc",
        source="live",
        event_time_us=event_time_us,
        escalated_time_us=event_time_us + 100,
    )


def _response(**overrides) -> AdjudicateResponse:
    defaults = {
        "decision": "BLOCK",
        "score_toxic": 0.9,
        "score_severe": 0.7,
        "score_obscene": 0.1,
        "score_threat": 0.8,
        "score_insult": 0.4,
        "score_identity": 0.2,
        "rationale": "explicit threat",
    }
    defaults.update(overrides)
    return AdjudicateResponse.model_validate(defaults)


def test_verdict_carries_through_message_fields():
    message = _message()
    verdict = build_verdict(message, _response(), provider="groq", prompt_version="adjudicate_v1")

    assert verdict.post_uri == message.post_uri
    assert verdict.author_hash == message.author_hash
    assert verdict.lang_predicted == message.lang_predicted
    assert verdict.lang_declared == message.lang_declared
    assert verdict.source == message.source
    assert verdict.event_time_us == message.event_time_us


def test_verdict_sets_resolved_tier_2_and_reuses_tier1_model_version():
    message = _message()
    verdict = build_verdict(message, _response(), provider="groq", prompt_version="adjudicate_v1")

    assert verdict.resolved_tier == 2
    assert verdict.model_version == message.tier1_model_version


def test_verdict_carries_provider_and_prompt_version():
    verdict = build_verdict(
        _message(), _response(), provider="gemini", prompt_version="adjudicate_v1"
    )

    assert verdict.adjudicator_provider == "gemini"
    assert verdict.prompt_version == "adjudicate_v1"


def test_verdict_scores_come_from_the_response():
    response = _response(score_toxic=0.42)
    verdict = build_verdict(_message(), response, provider="groq", prompt_version="adjudicate_v1")

    assert verdict.score_toxic == 0.42
    assert verdict.decision == "BLOCK"


def test_verdict_not_flagged_low_confidence_or_sampled_out():
    verdict = build_verdict(
        _message(), _response(), provider="groq", prompt_version="adjudicate_v1"
    )

    assert verdict.low_confidence is False
    assert verdict.escalation_sampled_out is False


def test_latency_is_never_negative_even_for_a_future_event_time():
    import time

    future_us = int(time.time() * 1_000_000) + 60_000_000
    verdict = build_verdict(
        _message(event_time_us=future_us),
        _response(),
        provider="groq",
        prompt_version="adjudicate_v1",
    )

    assert verdict.latency_ms == 0

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

import uuid6

from classifier.budget_guard import BudgetGuard
from classifier.tier0.classify import TIER0_MODEL_VERSION, Tier0Result
from classifier.tier0.classify import classify as tier0_classify
from classifier.tier0.lexicon import Lexicon
from classifier.tier1.model import Tier1Model, Tier1Result
from common.config import ClassifierSettings
from common.metrics import (
    classifier_escalated_total,
    classifier_escalation_sampled_out_total,
    classifier_score,
    classifier_tier0_resolved_total,
    classifier_tier1_batch_size,
    classifier_tier1_inference_seconds,
    classifier_tier1_seq_len,
)
from common.schemas import EscalateMessage, PostsRawMessage, Verdict


@dataclass(frozen=True)
class Thresholds:
    tau_lo: float
    tau_hi: float
    tau_mid: float


def resolve_thresholds(lang: str, settings: ClassifierSettings) -> Thresholds:
    """Per-language threshold override if one is configured for lang, else
    the global defaults."""
    override = settings.lang_threshold_overrides.get(lang, {})
    return Thresholds(
        tau_lo=override.get("tau_lo", settings.tau_lo),
        tau_hi=override.get("tau_hi", settings.tau_hi),
        tau_mid=override.get("tau_mid", settings.tau_mid),
    )


def _now_us() -> int:
    return int(time.time() * 1_000_000)


def _latency_ms(event_time_us: int, decided_time_us: int) -> int:
    return max(0, (decided_time_us - event_time_us) // 1000)


def _tier0_verdict(message: PostsRawMessage, tier0_result: Tier0Result) -> Verdict:
    decided_time_us = _now_us()
    decision: Literal["ALLOW", "BLOCK"]
    decision = "ALLOW" if tier0_result.decision == "HARD_ALLOW" else "BLOCK"
    return Verdict(
        id=str(uuid6.uuid7()),
        post_uri=message.post_uri,
        author_hash=message.author_hash,
        lang_predicted=message.lang_predicted,
        lang_declared=message.lang_declared,
        lang_confidence=message.lang_confidence,
        decision=decision,
        resolved_tier=0,
        model_version=TIER0_MODEL_VERSION,
        source=message.source,
        event_time_us=message.event_time_us,
        decided_time_us=decided_time_us,
        latency_ms=_latency_ms(message.event_time_us, decided_time_us),
    )


def _tier1_verdict(
    message: PostsRawMessage,
    tier1_result: Tier1Result,
    model_version: str,
    decision: Literal["ALLOW", "BLOCK"],
    *,
    low_confidence: bool = False,
    escalation_sampled_out: bool = False,
) -> Verdict:
    decided_time_us = _now_us()
    scores = tier1_result.scores
    return Verdict(
        id=str(uuid6.uuid7()),
        post_uri=message.post_uri,
        author_hash=message.author_hash,
        lang_predicted=message.lang_predicted,
        lang_declared=message.lang_declared,
        lang_confidence=message.lang_confidence,
        decision=decision,
        resolved_tier=1,
        score_toxic=scores["toxic"],
        score_severe=scores["severe_toxic"],
        score_obscene=scores["obscene"],
        score_threat=scores["threat"],
        score_insult=scores["insult"],
        score_identity=scores["identity_hate"],
        low_confidence=low_confidence,
        escalation_sampled_out=escalation_sampled_out,
        model_version=model_version,
        source=message.source,
        event_time_us=message.event_time_us,
        decided_time_us=decided_time_us,
        latency_ms=_latency_ms(message.event_time_us, decided_time_us),
    )


def _escalate_message(
    message: PostsRawMessage, tier1_result: Tier1Result, model_version: str
) -> EscalateMessage:
    scores = tier1_result.scores
    return EscalateMessage(
        id=str(uuid6.uuid7()),
        post_uri=message.post_uri,
        author_hash=message.author_hash,
        text=message.text,
        text_normalized=message.text_normalized,
        lang_predicted=message.lang_predicted,
        lang_declared=message.lang_declared,
        lang_confidence=message.lang_confidence,
        tier1_score_toxic=scores["toxic"],
        tier1_score_severe=scores["severe_toxic"],
        tier1_score_obscene=scores["obscene"],
        tier1_score_threat=scores["threat"],
        tier1_score_insult=scores["insult"],
        tier1_score_identity=scores["identity_hate"],
        tier1_model_version=model_version,
        source=message.source,
        event_time_us=message.event_time_us,
        escalated_time_us=_now_us(),
    )


async def decide(
    message: PostsRawMessage,
    *,
    lexicons: dict[str, Lexicon],
    tier1: Tier1Model,
    budget_guard: BudgetGuard,
    settings: ClassifierSettings,
) -> Verdict | EscalateMessage:
    """Runs the Tier 0 -> Tier 1 -> budget-guard cascade for one message."""
    tier0_result = tier0_classify(message, lexicons)
    classifier_tier0_resolved_total.labels(
        decision=tier0_result.decision, script=tier0_result.script
    ).inc()

    if tier0_result.decision != "PASS_TO_TIER1":
        return _tier0_verdict(message, tier0_result)

    start = time.perf_counter()
    tier1_result = await asyncio.to_thread(tier1.infer, message.text_normalized)
    classifier_tier1_inference_seconds.observe(time.perf_counter() - start)
    classifier_tier1_batch_size.observe(1)
    classifier_tier1_seq_len.observe(tier1_result.seq_len)

    p = tier1_result.scores["toxic"]
    classifier_score.observe(p)
    thresholds = resolve_thresholds(message.lang_predicted, settings)

    if p < thresholds.tau_lo:
        return _tier1_verdict(message, tier1_result, tier1.model_version, decision="ALLOW")
    if p > thresholds.tau_hi:
        return _tier1_verdict(message, tier1_result, tier1.model_version, decision="BLOCK")

    outcome = await budget_guard.decide(message.id)
    if outcome.escalate:
        classifier_escalated_total.labels(lang=message.lang_predicted).inc()
        return _escalate_message(message, tier1_result, tier1.model_version)

    classifier_escalation_sampled_out_total.labels(lang=message.lang_predicted).inc()
    sampled_out_decision: Literal["ALLOW", "BLOCK"]
    sampled_out_decision = "BLOCK" if p > thresholds.tau_mid else "ALLOW"
    return _tier1_verdict(
        message,
        tier1_result,
        tier1.model_version,
        decision=sampled_out_decision,
        low_confidence=True,
        escalation_sampled_out=True,
    )

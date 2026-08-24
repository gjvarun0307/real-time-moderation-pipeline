"""Building the final Tier 2 Verdict from a validated LLM response.
"""

import time

import uuid6

from common.schemas import AdjudicateResponse, EscalateMessage, Verdict


def build_verdict(
    message: EscalateMessage,
    response: AdjudicateResponse,
    *,
    provider: str,
    prompt_version: str,
) -> Verdict:
    decided_time_us = int(time.time() * 1_000_000)
    return Verdict(
        id=str(uuid6.uuid7()),
        post_uri=message.post_uri,
        author_hash=message.author_hash,
        lang_predicted=message.lang_predicted,
        lang_declared=message.lang_declared,
        lang_confidence=message.lang_confidence,
        decision=response.decision,
        resolved_tier=2,
        score_toxic=response.score_toxic,
        score_severe=response.score_severe,
        score_obscene=response.score_obscene,
        score_threat=response.score_threat,
        score_insult=response.score_insult,
        score_identity=response.score_identity,
        low_confidence=False,
        escalation_sampled_out=False,
        # Reuses the upstream Tier 1 model version — Verdict.model_version
        # is required with no LLM-specific alternative field.
        model_version=message.tier1_model_version,
        prompt_version=prompt_version,
        adjudicator_provider=provider,
        source=message.source,
        event_time_us=message.event_time_us,
        decided_time_us=decided_time_us,
        latency_ms=max(0, (decided_time_us - message.event_time_us) // 1000),
    )

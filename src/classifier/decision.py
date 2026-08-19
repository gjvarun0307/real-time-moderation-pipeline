import random
import time
from typing import Literal

import uuid6

from common.schemas import PostsRawMessage, Verdict

MODEL_VERSION = "stub-random-v0"


def decide_stub(message: PostsRawMessage) -> Verdict:
    """Placeholder decision for a post: no real model exists yet.

    Weighted rather than uniform so the decision mix looks like a
    plausible real cascade's output (mostly ALLOW) instead of drowning
    Postgres in BLOCK/REVIEW rows that selective persistence would
    otherwise always keep.
    """
    roll = random.random()
    decision: Literal["ALLOW", "BLOCK", "REVIEW"]
    if roll < 0.85:
        decision = "ALLOW"
    elif roll < 0.95:
        decision = "REVIEW"
    else:
        decision = "BLOCK"

    decided_time_us = int(time.time() * 1_000_000)
    latency_ms = max(0, (decided_time_us - message.event_time_us) // 1000)

    return Verdict(
        id=str(uuid6.uuid7()),
        post_uri=message.post_uri,
        author_hash=message.author_hash,
        lang_predicted=message.lang_predicted,
        lang_declared=message.lang_declared,
        lang_confidence=message.lang_confidence,
        decision=decision,
        resolved_tier=0,
        model_version=MODEL_VERSION,
        source=message.source,
        event_time_us=message.event_time_us,
        decided_time_us=decided_time_us,
        latency_ms=latency_ms,
    )

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class RawEvent(BaseModel):
    """One Jetstream frame, minimally typed.

    Deliberately permissive (extra="allow", commit/account/identity as
    plain dicts), a separate stage from the FirehoseSource this model supports.
    """

    model_config = ConfigDict(extra="allow")

    did: str
    time_us: int
    kind: str
    commit: dict[str, Any] | None = None
    account: dict[str, Any] | None = None
    identity: dict[str, Any] | None = None


class PostRecord(BaseModel):
    """The `record` payload of an app.bsky.feed.post commit. 
    """

    model_config = ConfigDict(extra="allow")

    text: str
    langs: list[str] | None = None
    createdAt: str | None = None


class Commit(BaseModel):
    """`record` is only present on create/update —
    delete commits reference an rkey with nothing else, so it's optional.
    """

    model_config = ConfigDict(extra="allow")

    rev: str
    operation: str
    collection: str
    rkey: str
    cid: str | None = None
    record: PostRecord | None = None


class PostsRawMessage(BaseModel):
    """The message produced to the `posts.raw` topic."""

    id: str
    post_uri: str
    author_hash: str
    text: str
    text_normalized: str
    lang_declared: str | None
    lang_declared_raw: str | None
    lang_predicted: str
    lang_confidence: float
    event_time_us: int
    ingest_time_us: int
    char_len: int
    has_emoji: bool
    source: Literal["live", "replay"]
    schema_version: int = 2


class Verdict(BaseModel):
    """A moderation decision for one post — produced to `moderation.verdicts`
    and, selectively, persisted to Postgres.
    """

    id: str
    post_uri: str
    author_hash: str
    lang_predicted: str
    lang_declared: str | None
    lang_confidence: float
    decision: Literal["ALLOW", "BLOCK", "REVIEW"]
    resolved_tier: int
    score_toxic: float | None = None
    score_severe: float | None = None
    score_obscene: float | None = None
    score_threat: float | None = None
    score_insult: float | None = None
    score_identity: float | None = None
    low_confidence: bool = False
    escalation_sampled_out: bool = False
    model_version: str
    prompt_version: str | None = None
    adjudicator_provider: str | None = None
    source: Literal["live", "replay"]
    event_time_us: int
    decided_time_us: int
    latency_ms: int
    schema_version: int = 1


class EscalateMessage(BaseModel):
    """A post routed to LLM adjudication after Tier 1 placed it in the
    uncertain band — produced to `moderation.escalate`.
    """

    id: str
    post_uri: str
    author_hash: str
    text: str
    text_normalized: str
    lang_predicted: str
    lang_declared: str | None
    lang_confidence: float
    tier1_score_toxic: float
    tier1_score_severe: float | None = None
    tier1_score_obscene: float | None = None
    tier1_score_threat: float | None = None
    tier1_score_insult: float | None = None
    tier1_score_identity: float | None = None
    tier1_model_version: str
    source: Literal["live", "replay"]
    event_time_us: int
    escalated_time_us: int
    schema_version: int = 1

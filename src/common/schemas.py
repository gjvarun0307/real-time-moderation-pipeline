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

from typing import Any

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

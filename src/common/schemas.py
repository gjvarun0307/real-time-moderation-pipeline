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

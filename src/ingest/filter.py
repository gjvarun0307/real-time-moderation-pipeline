from dataclasses import dataclass
from enum import StrEnum

from pydantic import ValidationError

from common.schemas import Commit, PostRecord, RawEvent

SCHEMA_INVALID = "schema_invalid"


class DropReason(StrEnum):
    """Only SCHEMA_INVALID is a DLQ case; these are expected,
    in-scope-but-not-usable traffic, not anomalies.
    """

    NOT_COMMIT = "not_commit"
    WRONG_COLLECTION = "wrong_collection"
    EMPTY_TEXT = "empty_text"


@dataclass
class Accepted:
    commit: Commit
    post: PostRecord


@dataclass
class Rejected:
    reason: str
    is_dlq: bool


FilterResult = Accepted | Rejected


def classify(event: RawEvent, wanted_collection: str) -> FilterResult:
    """Order matters: cheap structural checks
    """
    if event.kind != "commit":
        return Rejected(reason=DropReason.NOT_COMMIT, is_dlq=False)

    if event.commit is None:
        # kind=="commit" without a commit payload violates Jetstream's
        # own contract — malformed, not just out-of-scope.
        return Rejected(reason=SCHEMA_INVALID, is_dlq=True)

    try:
        commit = Commit.model_validate(event.commit)
    except ValidationError:
        return Rejected(reason=SCHEMA_INVALID, is_dlq=True)

    if commit.operation != "create":
        # keeps the operation so the exclusion is countable per-op
        # (delete vs update), not just lumped together.
        return Rejected(reason=f"op_{commit.operation}", is_dlq=False)

    if commit.collection != wanted_collection:
        return Rejected(reason=DropReason.WRONG_COLLECTION, is_dlq=False)

    if commit.record is None:
        # create op with no record body — also malformed, not just out-of-scope.
        return Rejected(reason=SCHEMA_INVALID, is_dlq=True)

    if not commit.record.text.strip():
        return Rejected(reason=DropReason.EMPTY_TEXT, is_dlq=False)

    return Accepted(commit=commit, post=commit.record)

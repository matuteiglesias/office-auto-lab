"""Read-only X actor observation: portable, provider-independent v0.1 contracts."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

SCHEMA_EVENT = "x.observer.event.v0.1"
SCHEMA_POST = "x.observer.post.v0.1"
SCHEMA_PAGE = "x.observer.page.v0.1"
EVENT_TYPES = frozenset(("ORIGINAL", "REPOST", "QUOTE", "REPLY", "MIXED", "UNKNOWN"))
NUMERIC_ID = re.compile(r"^[0-9]{1,19}$")


class ObserverContractError(ValueError):
    """Provider evidence cannot safely be represented in the frozen contract."""


def numeric_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not NUMERIC_ID.fullmatch(value):
        raise ObserverContractError(f"{label} must be a numeric X ID")
    return value


@dataclass(frozen=True)
class Reference:
    type: str
    post_id: str
    author_id: str | None = None
    availability: str = "UNKNOWN"

    def __post_init__(self) -> None:
        numeric_id(self.post_id, "reference post ID")
        if self.author_id is not None:
            numeric_id(self.author_id, "reference author ID")


@dataclass(frozen=True)
class ActivityEvent:
    event_id: str
    observed_user_id: str
    activity_post_id: str
    event_type: Literal["ORIGINAL", "REPOST", "QUOTE", "REPLY", "MIXED", "UNKNOWN"]
    created_at_utc: str | None
    references: tuple[Reference, ...]
    source_run_id: str
    source_page_sha256: str
    evidence_status: str = "OBSERVED"
    schema_version: str = SCHEMA_EVENT

    def __post_init__(self) -> None:
        numeric_id(self.observed_user_id, "observed user ID")
        numeric_id(self.activity_post_id, "activity post ID")
        if self.event_id != f"xevt:{self.observed_user_id}:{self.activity_post_id}":
            raise ObserverContractError("event identity is not stable actor/activity ID")
        if self.event_type not in EVENT_TYPES:
            raise ObserverContractError("unknown event type")

    def record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ObservedPost:
    post_id: str
    author_id: str | None
    text: str | None
    created_at_utc: str | None
    references: tuple[Reference, ...]
    edit_history: tuple[str, ...]
    availability: str
    content_sha256: str | None
    source_page_sha256: str
    schema_version: str = SCHEMA_POST

    def __post_init__(self) -> None:
        numeric_id(self.post_id, "post ID")
        if self.author_id is not None:
            numeric_id(self.author_id, "post author ID")

    def record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedPage:
    observed_user_id: str
    events: tuple[ActivityEvent, ...]
    posts: tuple[ObservedPost, ...]
    next_token: str | None
    page_sha256: str
    partial: bool
    errors_count: int
    result_count: int | None
    schema_version: str = SCHEMA_PAGE

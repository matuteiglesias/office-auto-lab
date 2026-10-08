"""Bounded incremental planning for the read-only X observer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .contracts import ObserverContractError, numeric_id


@dataclass(frozen=True)
class ObservationPlan:
    user_id: str
    max_pages: int = 2
    max_results: int = 10
    overlap: timedelta = timedelta(minutes=30)
    since_id: str | None = None
    pagination_token: str | None = None

    def __post_init__(self) -> None:
        numeric_id(self.user_id, "observed user ID")
        if not 1 <= self.max_pages <= 100:
            raise ObserverContractError("max_pages must be 1..100")
        if not 5 <= self.max_results <= 100:
            raise ObserverContractError("max_results must be 5..100")
        if self.overlap < timedelta(0) or self.overlap > timedelta(days=7):
            raise ObserverContractError("overlap must be between 0 and 7 days")
        if self.since_id is not None:
            numeric_id(self.since_id, "since_id")


def overlap_start(last_success_at: str | None, overlap: timedelta) -> str | None:
    if not last_success_at:
        return None
    try:
        value = datetime.fromisoformat(last_success_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObserverContractError("cursor last_success_at is not ISO8601") from exc
    if value.tzinfo is None:
        raise ObserverContractError("cursor last_success_at lacks timezone")
    return (value.astimezone(timezone.utc) - overlap).isoformat().replace("+00:00", "Z")

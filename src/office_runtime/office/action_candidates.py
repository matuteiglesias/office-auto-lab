"""Observational, bounded action-candidate evidence for Staff preparation."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from .action_contracts import ActionContractError, validate_action_contract


SCHEMA_VERSION = "ops.staff-action-candidate.v1"
FRESH_STATUSES = frozenset({"CURRENT", "FRESH"})
MAX_CANDIDATES_PER_FRONT = 3


class ActionCandidateError(ValueError):
    pass


class ActionCandidateProducer(Protocol):
    """A producer proposes observations; it never creates a ready pull."""

    name: str

    def produce(self, snapshot: dict, work_item: dict) -> list[dict]:
        ...


def _digest(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def validate_action_candidate(value: Any, *, front_id: str) -> dict:
    """Validate a portable observation before Staff considers it."""
    if not isinstance(value, dict):
        raise ActionCandidateError("candidate must be an object")
    candidate = dict(value)
    if str(candidate.get("schema_version", SCHEMA_VERSION)) != SCHEMA_VERSION:
        raise ActionCandidateError("candidate has unsupported schema")
    for key in ("candidate_id", "front_id", "producer", "generated_at", "objective", "why_now", "scope_boundary"):
        if not str(candidate.get(key, "")).strip():
            raise ActionCandidateError(f"candidate is missing {key}")
    if str(candidate["front_id"]) != str(front_id):
        raise ActionCandidateError("candidate belongs to a different front")
    if not isinstance(candidate.get("source_evidence"), list) or not candidate["source_evidence"]:
        raise ActionCandidateError("candidate has no source evidence")
    if str(candidate.get("source_freshness", "")).upper() not in FRESH_STATUSES:
        raise ActionCandidateError("candidate source evidence is stale or unknown")
    contract = validate_action_contract(candidate, front_id=front_id)
    candidate.update(contract)
    candidate["schema_version"] = SCHEMA_VERSION
    candidate["candidate_digest"] = _digest({key: value for key, value in candidate.items() if key != "candidate_digest"})
    return candidate


def bounded_candidates(values: list[dict], *, front_id: str) -> tuple[list[dict], list[str]]:
    """Deterministically retain a small candidate set and report rejection facts."""
    accepted: list[dict] = []
    rejected: list[str] = []
    for value in sorted((dict(row) for row in values if isinstance(row, dict)), key=lambda row: str(row.get("candidate_id", ""))):
        try:
            accepted.append(validate_action_candidate(value, front_id=front_id))
        except (ActionCandidateError, ActionContractError) as exc:
            rejected.append(f"{value.get('candidate_id', '<unnamed>')}: {exc}")
    return accepted[:MAX_CANDIDATES_PER_FRONT], rejected


class StaticCandidateProducer:
    """Generic producer for already-materialized governed candidate records.

    A caller/adaptor supplies records from a bounded repository artifact,
    control-plane QA artifact, or connected-context export.  The producer does
    not inspect prose or external services and cannot change Office state.
    """

    def __init__(self, name: str, records: list[dict] | None = None) -> None:
        self.name = name
        self._records = list(records or [])

    def produce(self, snapshot: dict, work_item: dict) -> list[dict]:
        front_id = str(work_item.get("front_id", ""))
        return [dict(row) for row in self._records if str(row.get("front_id", "")) == front_id]


class RepositoryEvidenceProducer(StaticCandidateProducer):
    def __init__(self, records: list[dict] | None = None) -> None:
        super().__init__("REPOSITORY_EVIDENCE", records)


class ControlPlaneEvidenceProducer(StaticCandidateProducer):
    def __init__(self, records: list[dict] | None = None) -> None:
        super().__init__("CONTROL_PLANE_EVIDENCE", records)


class ConnectedContextEvidenceProducer(StaticCandidateProducer):
    def __init__(self, records: list[dict] | None = None) -> None:
        super().__init__("CONNECTED_CONTEXT_EVIDENCE", records)

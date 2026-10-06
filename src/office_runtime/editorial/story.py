from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

from .contracts import ActivityEvidence, ContractError, StoryCluster


@dataclass(frozen=True)
class ExplicitStoryRelation:
    relation_id: str
    evidence_refs: tuple[str, ...]
    relation_kind: str
    provenance_ref: str

    def __post_init__(self) -> None:
        if not self.relation_id.strip():
            raise ContractError("story relation_id must be non-empty")
        if len(self.evidence_refs) < 2 or len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ContractError("explicit story relations require at least two distinct evidence refs")
        if not self.relation_kind.strip():
            raise ContractError("story relation_kind must be non-empty")
        if not self.provenance_ref.strip():
            raise ContractError("story relation requires an inspectable provenance_ref")


def deterministic_story_id(evidence_refs: Sequence[str], cluster_kind: str) -> str:
    refs = sorted(set(evidence_refs))
    if not refs:
        raise ContractError("story IDs require at least one evidence ref")
    if len(refs) != len(evidence_refs):
        raise ContractError("story evidence refs must be unique")
    payload = json.dumps(
        {"cluster_kind": cluster_kind, "evidence_refs": refs},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"story:sha256:{hashlib.sha256(payload).hexdigest()[:24]}"


def cluster_stories(
    evidence: Iterable[ActivityEvidence],
    *,
    explicit_relations: Sequence[ExplicitStoryRelation] = (),
    as_of: str | None = None,
) -> tuple[StoryCluster, ...]:
    items = {item.evidence_id: item for item in evidence}
    if not items:
        return ()

    assigned: set[str] = set()
    stories: list[StoryCluster] = []
    for relation in sorted(explicit_relations, key=lambda value: value.relation_id):
        missing = set(relation.evidence_refs) - set(items)
        if missing:
            raise ContractError(
                f"story relation {relation.relation_id!r} references unknown evidence: {sorted(missing)}"
            )
        overlap = assigned & set(relation.evidence_refs)
        if overlap:
            raise ContractError(
                f"story relation {relation.relation_id!r} overlaps already clustered evidence: {sorted(overlap)}"
            )
        grouped = [items[ref] for ref in relation.evidence_refs]
        stories.append(
            _build_story(
                grouped,
                cluster_kind=f"explicit:{relation.relation_kind}",
                related_context_refs=(relation.provenance_ref,),
                as_of=as_of,
            )
        )
        assigned.update(relation.evidence_refs)

    for evidence_id in sorted(set(items) - assigned):
        stories.append(_build_story([items[evidence_id]], cluster_kind="single_event", as_of=as_of))

    return tuple(sorted(stories, key=lambda item: item.story_id))


def _build_story(
    items: Sequence[ActivityEvidence],
    *,
    cluster_kind: str,
    related_context_refs: Sequence[str] = (),
    as_of: str | None,
) -> StoryCluster:
    refs = tuple(sorted(item.evidence_id for item in items))
    repositories = tuple(sorted({item.repository_ref for item in items}))
    constraints = tuple(sorted(set(
        constraint
        for item in items
        if (constraint := _status_constraint(item.status))
    )))
    summary = " | ".join(item.title for item in sorted(items, key=lambda item: item.evidence_id))
    if len(summary) > 600:
        summary = summary[:597].rstrip() + "..."
    return StoryCluster(
        story_id=deterministic_story_id(refs, cluster_kind),
        evidence_refs=refs,
        cluster_kind=cluster_kind,
        working_summary=summary,
        freshness_class=_freshness_class(items, as_of=as_of),
        repository_refs=repositories,
        public_eligibility=_combined_public_eligibility(items),
        related_context_refs=tuple(related_context_refs),
        status_language_constraints=constraints,
    )


def _combined_public_eligibility(items: Sequence[ActivityEvidence]) -> str:
    values = {item.public_eligibility for item in items}
    if "restricted" in values:
        return "restricted"
    if "unknown" in values:
        return "unknown"
    return "eligible"


def _freshness_class(items: Sequence[ActivityEvidence], *, as_of: str | None) -> str:
    now = _parse_time(as_of) if as_of else datetime.now(timezone.utc)
    latest = max(_parse_time(item.event_at) for item in items)
    age_seconds = max(0.0, (now - latest).total_seconds())
    if age_seconds <= 72 * 3600:
        return "timely"
    if age_seconds <= 14 * 24 * 3600:
        return "recent"
    return "evergreen"


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ContractError("story timestamps must be timezone-aware")
    return parsed


def _status_constraint(status: str) -> str | None:
    return {
        "in_progress": "describe this work as in progress, not shipped",
        "unknown": "do not imply completion while source status is unknown",
        "failed": "describe the observed failure; do not imply successful resolution",
        "waiting": "preserve WAITING status unless separate evidence proves completion",
        "dropped": "preserve dropped/cancelled status; do not describe as shipped",
        "superseded": "preserve superseded status and avoid presenting it as current",
    }.get(status)

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from .validation import GATE_NAMES, QUALITY_NAMES, semantic_fingerprint as _semantic_fingerprint

DAILY_BATCH_SCHEMA = "office_runtime.editorial.daily_batch.v1"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "with"}
)


@dataclass(frozen=True)
class BatchConfig:
    target: int = 8
    floor: int = 5
    ceiling: int = 12
    max_per_source_event: int = 2
    near_duplicate_threshold: float = 0.82
    max_fallback_passes: int = 4

    def validate(self) -> None:
        if not 0 < self.floor <= self.target <= self.ceiling:
            raise ValueError("batch counts must satisfy 0 < floor <= target <= ceiling")
        if self.max_per_source_event < 1:
            raise ValueError("max_per_source_event must be positive")
        if not 0.0 < self.near_duplicate_threshold <= 1.0:
            raise ValueError("near_duplicate_threshold must be in (0, 1]")
        if self.max_fallback_passes < 0:
            raise ValueError("max_fallback_passes cannot be negative")


@dataclass(frozen=True)
class FallbackPool:
    name: str
    candidates: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class BatchCompilation:
    batch: Mapping[str, Any]
    selected_candidates: tuple[Mapping[str, Any], ...]
    fallback_requests: tuple[str, ...]
    rejected: tuple[Mapping[str, Any], ...]


def semantic_fingerprint(candidate: Mapping[str, Any]) -> str:
    existing = candidate.get("semantic_fingerprint")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    claim = candidate.get("claim") or candidate.get("text")
    family = candidate.get("candidate_family", "field_note")
    refs = candidate.get("evidence_refs", [])
    if not isinstance(claim, str) or not isinstance(family, str) or not isinstance(refs, list):
        raise ValueError("candidate lacks fields needed for semantic fingerprint")
    return _semantic_fingerprint(claim=claim, family=family, evidence_refs=refs)


def compile_daily_batch(
    *,
    primary_candidates: Sequence[Mapping[str, Any]],
    batch_date: str | date,
    profile_id: str = "dev",
    recent_history: Sequence[Mapping[str, Any]] = (),
    fallback_pools: Sequence[FallbackPool] = (),
    config: BatchConfig = BatchConfig(),
) -> BatchCompilation:
    config.validate()
    day = date.fromisoformat(batch_date) if isinstance(batch_date, str) else batch_date
    if not isinstance(day, date):
        raise TypeError("batch_date must be ISO date text or date")

    recent_fingerprints = {
        semantic_fingerprint(item) for item in recent_history if _can_fingerprint(item)
    }
    recent_claims = [_tokens(_claim(item)) for item in recent_history if _claim(item)]
    rejected: list[dict[str, Any]] = []
    selected: list[Mapping[str, Any]] = []
    source_counts: Counter[str] = Counter()
    seen_fingerprints: set[str] = set()
    seen_claims: list[set[str]] = []
    fallback_requests: list[str] = []

    def consider(pool: Sequence[Mapping[str, Any]], source_label: str) -> None:
        remaining = [dict(candidate) for candidate in pool]
        while remaining and len(selected) < config.target and len(selected) < config.ceiling:
            ranked = sorted(
                remaining,
                key=lambda candidate: _rank_key(candidate, selected),
                reverse=True,
            )
            candidate = ranked[0]
            remaining.remove(candidate)
            reason = _rejection_reason(
                candidate,
                day=day,
                recent_fingerprints=recent_fingerprints,
                recent_claims=recent_claims,
                seen_fingerprints=seen_fingerprints,
                seen_claims=seen_claims,
                source_counts=source_counts,
                config=config,
            )
            if reason is not None:
                rejected.append(
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "source_pool": source_label,
                        "reason": reason,
                    }
                )
                continue
            fingerprint = semantic_fingerprint(candidate)
            claim_tokens = _tokens(_claim(candidate))
            selected.append(candidate)
            seen_fingerprints.add(fingerprint)
            seen_claims.append(claim_tokens)
            for ref in _source_events(candidate):
                source_counts[ref] += 1

    consider(primary_candidates, "primary")
    for pool in fallback_pools[: config.max_fallback_passes]:
        if len(selected) >= config.target:
            break
        fallback_requests.append(pool.name)
        consider(pool.candidates, pool.name)

    inventory_status = "HEALTHY" if len(selected) >= config.floor else "DEGRADED_INVENTORY"
    shortages: list[str] = []
    if len(selected) < config.floor:
        shortages.append(
            f"defensible_candidates_below_floor:{len(selected)}/{config.floor}"
        )
        if len(fallback_requests) >= min(len(fallback_pools), config.max_fallback_passes):
            shortages.append("eligible_fallback_pools_exhausted")
        reason_counts = Counter(item["reason"] for item in rejected)
        shortages.extend(f"rejected_{reason}:{count}" for reason, count in sorted(reason_counts.items()))

    source_tiers = Counter(str(candidate.get("source_tier", "unknown")) for candidate in selected)
    repos = sorted(
        {
            repo
            for candidate in selected
            for repo in _string_values(candidate.get("repository_refs"))
        }
    )
    families = sorted(
        {
            str(candidate.get("candidate_family"))
            for candidate in selected
            if candidate.get("candidate_family")
        }
    )
    career_signals = sorted(
        {
            signal
            for candidate in selected
            for signal in _string_values(candidate.get("career_signals"))
        }
    )
    batch_id = f"editorial:dev:{day.isoformat()}"
    batch = {
        "schema_version": DAILY_BATCH_SCHEMA,
        "batch_id": batch_id,
        "profile_id": profile_id,
        "batch_date": day.isoformat(),
        "target_count": config.target,
        "floor_count": config.floor,
        "ceiling_count": config.ceiling,
        "inventory_status": inventory_status,
        "candidate_ids": [candidate.get("candidate_id") for candidate in selected],
        "source_tier_counts": dict(sorted(source_tiers.items())),
        "diversity_summary": {
            "repository_refs": repos,
            "candidate_families": families,
            "career_signals": career_signals,
            "source_event_count": len(source_counts),
        },
        "shortage_reasons": shortages,
    }
    return BatchCompilation(
        batch=batch,
        selected_candidates=tuple(selected),
        fallback_requests=tuple(fallback_requests),
        rejected=tuple(rejected),
    )


def _rejection_reason(
    candidate: Mapping[str, Any],
    *,
    day: date,
    recent_fingerprints: set[str],
    recent_claims: Sequence[set[str]],
    seen_fingerprints: set[str],
    seen_claims: Sequence[set[str]],
    source_counts: Counter[str],
    config: BatchConfig,
) -> str | None:
    if candidate.get("machine_disposition") != "stage":
        return "not_stageable"
    gates = candidate.get("gates")
    if isinstance(gates, Mapping) and any(gates.get(name) == "FAIL" for name in GATE_NAMES):
        return "hard_gate_failed"
    expires_at = candidate.get("expires_at")
    if isinstance(expires_at, str) and expires_at.strip():
        if _expiry_date(expires_at) < day:
            return "expired"
    fingerprint = semantic_fingerprint(candidate)
    if fingerprint in recent_fingerprints:
        return "recent_fingerprint_repeat"
    if fingerprint in seen_fingerprints:
        return "same_batch_fingerprint_repeat"

    claim_tokens = _tokens(_claim(candidate))
    if claim_tokens and any(
        _jaccard(claim_tokens, previous) >= config.near_duplicate_threshold
        for previous in [*recent_claims, *seen_claims]
        if previous
    ):
        return "near_duplicate"

    events = _source_events(candidate)
    if events and any(source_counts[event] >= config.max_per_source_event for event in events):
        return "source_concentration"
    return None


def _rank_key(candidate: Mapping[str, Any], selected: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
    existing_repos = {
        repo for item in selected for repo in _string_values(item.get("repository_refs"))
    }
    existing_families = {str(item.get("candidate_family")) for item in selected}
    repos = set(_string_values(candidate.get("repository_refs")))
    family = str(candidate.get("candidate_family", ""))
    diversity_bonus = (2 if repos - existing_repos else 0) + (1 if family not in existing_families else 0)
    quality = candidate.get("quality")
    quality_total = 0
    if isinstance(quality, Mapping):
        quality_total = sum(
            int(quality.get(name, 0))
            for name in QUALITY_NAMES
            if isinstance(quality.get(name, 0), int)
        )
    freshness = {"timely": 3, "recent": 2, "evergreen": 1}.get(
        str(candidate.get("freshness_class", "")), 0
    )
    return (
        quality_total,
        diversity_bonus,
        freshness,
        str(candidate.get("generated_at", "")),
        str(candidate.get("candidate_id", "")),
    )


def _source_events(candidate: Mapping[str, Any]) -> list[str]:
    for key in ("source_event_refs", "work_refs", "evidence_refs"):
        values = _string_values(candidate.get(key))
        if values:
            return values
    return []


def _claim(candidate: Mapping[str, Any]) -> str:
    value = candidate.get("claim") or candidate.get("text")
    return value.strip() if isinstance(value, str) else ""


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS}


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _expiry_date(value: str) -> date:
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return date.fromisoformat(value[:10])


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _can_fingerprint(candidate: Mapping[str, Any]) -> bool:
    try:
        semantic_fingerprint(candidate)
    except (TypeError, ValueError):
        return False
    return True

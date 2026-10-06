from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

PROFILE_SCHEMA = "office_runtime.editorial.profile.v1"
CANDIDATE_SCHEMA = "office_runtime.editorial.candidate.v1"
SUPPORTED_STRATEGIES = frozenset({"dev_projection", "argentina_econ"})
ARGENTINA_ECON_RELATIONS = frozenset(
    {
        "supports",
        "contextualizes",
        "complicates",
        "contradicts",
        "historicizes",
        "cannot_adjudicate",
    }
)
RISK_CLASSES = frozenset({"low", "medium", "high"})


class ContractError(ValueError):
    pass


def projection_profiles_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "editorial" / "profiles.json"


def load_projection_profiles(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    source = Path(path) if path is not None else projection_profiles_path()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ContractError("profiles document must be an object")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ContractError("profiles document requires a non-empty profiles array")

    validated: dict[str, dict[str, Any]] = {}
    for raw in profiles:
        profile = validate_projection_profile(raw)
        profile_id = profile["profile_id"]
        if profile_id in validated:
            raise ContractError(f"duplicate projection profile {profile_id!r}")
        validated[profile_id] = profile
    return validated


def validate_projection_profile(value: Any) -> dict[str, Any]:
    profile = _mapping(value, "profile")
    required = {
        "schema_version",
        "profile_id",
        "account_key",
        "strategy",
        "public_identity",
        "sources",
        "fallback",
        "publication",
    }
    missing = required - set(profile)
    if missing:
        raise ContractError(f"projection profile missing keys: {sorted(missing)}")
    if profile["schema_version"] != PROFILE_SCHEMA:
        raise ContractError("unsupported projection profile schema_version")

    profile_id = _string(profile["profile_id"], "profile_id")
    _string(profile["account_key"], "account_key")
    strategy = _string(profile["strategy"], "strategy")
    if strategy not in SUPPORTED_STRATEGIES:
        raise ContractError(f"unsupported projection strategy {strategy!r}")

    identity = _mapping(profile["public_identity"], "public_identity")
    _string(identity.get("role"), "public_identity.role")
    handle = identity.get("x_handle")
    handle_env = identity.get("x_handle_env")
    if not _optional_string(handle) and not _optional_string(handle_env):
        raise ContractError("public_identity requires x_handle or x_handle_env")

    sources = _string_list(profile["sources"], "sources")
    publication = _mapping(profile["publication"], "publication")
    if publication.get("default_mode") not in {"dry_run", "publish_if_safe"}:
        raise ContractError("publication.default_mode must be dry_run or publish_if_safe")
    max_posts = publication.get("max_posts_per_day")
    if not isinstance(max_posts, int) or max_posts < 0 or max_posts > 4:
        raise ContractError("publication.max_posts_per_day must be an integer from 0 to 4")
    if publication.get("auto_publish_max_risk") != "low":
        raise ContractError("v1 auto publication may only allow low-risk candidates")

    if strategy == "dev_projection":
        if "github_estate" not in sources:
            raise ContractError("dev_projection requires github_estate source")
        if profile["fallback"] != "historical_dev_work":
            raise ContractError("dev_projection fallback must be historical_dev_work")
    elif strategy == "argentina_econ":
        required_sources = {
            "media_monitor",
            "atlas_economico_ar",
            "owned_economic_artifacts",
            "approved_idea_bank",
            "public_web_context",
        }
        if not required_sources.issubset(set(sources)):
            raise ContractError(
                "argentina_econ requires media, owned evidence, idea-bank and public-context sources"
            )
        if profile["fallback"] != "skip":
            raise ContractError("argentina_econ fallback must be skip")
        relations = profile.get("allowed_relations")
        if set(_string_list(relations, "allowed_relations")) != ARGENTINA_ECON_RELATIONS:
            raise ContractError("argentina_econ relation taxonomy must be complete and exact")

    return dict(profile)


def validate_candidate(value: Any, profile: Mapping[str, Any]) -> dict[str, Any]:
    candidate = _mapping(value, "candidate")
    required = {
        "schema_version",
        "candidate_id",
        "profile_id",
        "text",
        "risk_class",
        "evidence_refs",
    }
    missing = required - set(candidate)
    if missing:
        raise ContractError(f"editorial candidate missing keys: {sorted(missing)}")
    if candidate["schema_version"] != CANDIDATE_SCHEMA:
        raise ContractError("unsupported editorial candidate schema_version")
    _string(candidate["candidate_id"], "candidate_id")
    if candidate["profile_id"] != profile["profile_id"]:
        raise ContractError("candidate profile_id does not match projection profile")
    _string(candidate["text"], "text")
    if candidate["risk_class"] not in RISK_CLASSES:
        raise ContractError("candidate risk_class is invalid")
    _string_list(candidate["evidence_refs"], "evidence_refs")

    strategy = profile["strategy"]
    if strategy == "dev_projection":
        _string_list(candidate.get("work_refs"), "work_refs")
    elif strategy == "argentina_econ":
        _string(candidate.get("current_claim_ref"), "current_claim_ref")
        _string_list(candidate.get("owned_evidence_refs"), "owned_evidence_refs")
        _string_list(candidate.get("approved_idea_refs"), "approved_idea_refs")
        relation = candidate.get("relation")
        if relation not in ARGENTINA_ECON_RELATIONS:
            raise ContractError("argentina_econ candidate relation is invalid")
        if relation == "cannot_adjudicate":
            raise ContractError("cannot_adjudicate is a retrieval outcome, not publishable candidate copy")

    return dict(candidate)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{label} must be a non-empty string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractError(f"{label} must contain only non-empty strings")
    return list(value)


# Editorial Dev Staging v1 durable contracts.  Keep validate_candidate() above as
# the stable W0 seam; W1 callers opt into validate_dev_candidate().
import re as _editorial_re
from dataclasses import dataclass as _editorial_dataclass, field as _editorial_field
from datetime import datetime as _editorial_datetime

ACTIVITY_EVIDENCE_SCHEMA = "office_runtime.editorial.activity_evidence.v1"
STORY_CLUSTER_SCHEMA = "office_runtime.editorial.story_cluster.v1"
ANGLE_SCHEMA = "office_runtime.editorial.angle.v1"
DAILY_BATCH_SCHEMA = "office_runtime.editorial.daily_batch.v1"
RUN_BUNDLE_SCHEMA = "editorial.run_bundle.v1"

EVIDENCE_SOURCE_KINDS = frozenset({
    "github_pr", "github_release", "github_commit", "github_issue_decision",
    "office_run_evidence", "producer_receipt", "durable_artifact",
    "historical_dev_work",
})
EVIDENCE_STATUSES = frozenset({
    "completed", "merged", "released", "in_progress", "failed", "waiting",
    "dropped", "superseded", "unknown",
})
VISIBILITIES = frozenset({"public", "private", "internal", "unknown"})
PUBLIC_ELIGIBILITY = frozenset({"eligible", "restricted", "unknown"})
ANGLE_TYPES = frozenset({
    "lesson", "artifact", "question", "failure", "tradeoff", "measurement",
    "field_note", "synthesis",
})
CANDIDATE_FAMILIES = frozenset(value.upper() for value in ANGLE_TYPES)
FRESHNESS_CLASSES = frozenset({"timely", "recent", "evergreen"})
MACHINE_DISPOSITIONS = frozenset({"stage", "hold", "drop"})
GATE_RESULTS = frozenset({"pass", "hold", "fail", "unknown"})
INVENTORY_STATUSES = frozenset({"HEALTHY", "DEGRADED_INVENTORY", "FAILED"})
RUN_STATUSES = frozenset({
    "RETRIEVAL_ONLY", "HEALTHY", "DEGRADED_INVENTORY",
    "PARTIAL_SOURCE_FAILURE", "FAILED",
})
QUALITY_DIMENSIONS = (
    "evidence", "specificity", "external_usefulness", "novelty",
    "professional_signal",
)
_EDITORIAL_HEX_64 = _editorial_re.compile(r"^[0-9a-f]{64}$")


def _editorial_strings(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "" if allow_empty else " non-empty"
        raise ContractError(f"{label} must be a{qualifier} string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractError(f"{label} must contain only non-empty strings")
    return [item.strip() for item in value]


def _editorial_timestamp(value: Any, label: str) -> str:
    text = _string(value, label)
    try:
        parsed = _editorial_datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{label} must include a timezone")
    return text


def _editorial_date(value: Any, label: str) -> str:
    text = _string(value, label)
    try:
        _editorial_datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ContractError(f"{label} must be YYYY-MM-DD") from exc
    return text


def validate_activity_evidence(value: Any) -> dict[str, Any]:
    evidence = _mapping(value, "activity evidence")
    required = {
        "schema_version", "evidence_id", "source_kind", "source_ref",
        "observed_at", "event_at", "status", "title", "summary",
        "repository_ref", "visibility", "public_eligibility", "artifact_refs",
    }
    missing = required - set(evidence)
    if missing:
        raise ContractError(f"activity evidence missing keys: {sorted(missing)}")
    if evidence["schema_version"] != ACTIVITY_EVIDENCE_SCHEMA:
        raise ContractError("unsupported activity evidence schema_version")
    for key in ("evidence_id", "source_ref", "title", "summary", "repository_ref"):
        _string(evidence[key], key)
    _editorial_timestamp(evidence["observed_at"], "observed_at")
    _editorial_timestamp(evidence["event_at"], "event_at")
    if evidence["source_kind"] not in EVIDENCE_SOURCE_KINDS:
        raise ContractError("source_kind is invalid")
    if evidence["status"] not in EVIDENCE_STATUSES:
        raise ContractError("status is invalid")
    if evidence["visibility"] not in VISIBILITIES:
        raise ContractError("visibility is invalid")
    if evidence["public_eligibility"] not in PUBLIC_ELIGIBILITY:
        raise ContractError("public_eligibility is invalid")
    _editorial_strings(evidence["artifact_refs"], "artifact_refs", allow_empty=True)
    metadata = _mapping(evidence.get("source_metadata", {}), "source_metadata")
    for key, item in metadata.items():
        _string(key, "source_metadata key")
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ContractError("source_metadata values must be JSON scalars")
    return dict(evidence)


def validate_story_cluster(value: Any) -> dict[str, Any]:
    story = _mapping(value, "story cluster")
    required = {
        "schema_version", "story_id", "evidence_refs", "cluster_kind",
        "working_summary", "freshness_class", "repository_refs",
        "public_eligibility",
    }
    missing = required - set(story)
    if missing:
        raise ContractError(f"story cluster missing keys: {sorted(missing)}")
    if story["schema_version"] != STORY_CLUSTER_SCHEMA:
        raise ContractError("unsupported story cluster schema_version")
    _string(story["story_id"], "story_id")
    refs = _editorial_strings(story["evidence_refs"], "evidence_refs")
    if len(refs) != len(set(refs)):
        raise ContractError("story evidence_refs must be unique")
    _string(story["cluster_kind"], "cluster_kind")
    _string(story["working_summary"], "working_summary")
    if story["freshness_class"] not in FRESHNESS_CLASSES:
        raise ContractError("freshness_class is invalid")
    _editorial_strings(story["repository_refs"], "repository_refs")
    if story["public_eligibility"] not in PUBLIC_ELIGIBILITY:
        raise ContractError("public_eligibility is invalid")
    for key in (
        "related_context_refs", "measured_results", "open_questions",
        "status_language_constraints",
    ):
        _editorial_strings(story.get(key, []), key, allow_empty=True)
    return dict(story)


def validate_angle(value: Any) -> dict[str, Any]:
    angle = _mapping(value, "angle")
    required = {
        "schema_version", "angle_id", "story_id", "angle_type", "claim",
        "tension_or_hook", "transferable_lesson", "evidence_refs", "audience",
        "career_signals", "why_interesting", "risk_class",
    }
    missing = required - set(angle)
    if missing:
        raise ContractError(f"angle missing keys: {sorted(missing)}")
    if angle["schema_version"] != ANGLE_SCHEMA:
        raise ContractError("unsupported angle schema_version")
    for key in (
        "angle_id", "story_id", "claim", "tension_or_hook",
        "transferable_lesson", "why_interesting",
    ):
        _string(angle[key], key)
    if angle["angle_type"] not in ANGLE_TYPES:
        raise ContractError("angle_type is invalid")
    if angle["risk_class"] not in RISK_CLASSES:
        raise ContractError("angle risk_class is invalid")
    _editorial_strings(angle["evidence_refs"], "evidence_refs")
    _editorial_strings(angle["audience"], "audience")
    _editorial_strings(angle["career_signals"], "career_signals", allow_empty=True)
    for key in ("proof_object_refs", "required_status_wording"):
        _editorial_strings(angle.get(key, []), key, allow_empty=True)
    for key in ("counterpoint", "expiry_hint"):
        if angle.get(key) is not None:
            _string(angle[key], key)
    return dict(angle)


def validate_dev_candidate(value: Any, profile: Mapping[str, Any]) -> dict[str, Any]:
    candidate = validate_candidate(value, profile)
    if profile.get("strategy") != "dev_projection":
        raise ContractError("dev candidate extensions require dev_projection")
    required = {
        "story_id", "angle_id", "candidate_family", "semantic_fingerprint",
        "language", "topic_tags", "career_signals", "proof_object_refs",
        "freshness_class", "generated_at", "expires_at", "machine_disposition",
        "quality", "disclosure_risk", "repetition_risk", "status_truth_risk",
    }
    missing = required - set(candidate)
    if missing:
        raise ContractError(
            f"dev editorial candidate missing extension keys: {sorted(missing)}"
        )
    for key in ("story_id", "angle_id", "semantic_fingerprint", "language"):
        _string(candidate[key], key)
    if candidate["candidate_family"] not in CANDIDATE_FAMILIES:
        raise ContractError("candidate_family is invalid")
    for key in ("topic_tags", "career_signals", "proof_object_refs"):
        _editorial_strings(candidate[key], key, allow_empty=True)
    if candidate["freshness_class"] not in FRESHNESS_CLASSES:
        raise ContractError("candidate freshness_class is invalid")
    _editorial_timestamp(candidate["generated_at"], "generated_at")
    if candidate["expires_at"] is not None:
        _editorial_timestamp(candidate["expires_at"], "expires_at")
    if candidate["freshness_class"] == "timely" and candidate["expires_at"] is None:
        raise ContractError("timely candidates require expires_at")
    if candidate["machine_disposition"] not in MACHINE_DISPOSITIONS:
        raise ContractError("machine_disposition is invalid")
    quality = _mapping(candidate["quality"], "quality")
    if set(quality) != set(QUALITY_DIMENSIONS):
        raise ContractError(
            f"quality dimensions must be exactly {list(QUALITY_DIMENSIONS)!r}"
        )
    for key in QUALITY_DIMENSIONS:
        score = quality[key]
        if (
            not isinstance(score, int)
            or isinstance(score, bool)
            or not 0 <= score <= 4
        ):
            raise ContractError(f"quality.{key} must be an integer from 0 to 4")
    for gate in ("disclosure_risk", "repetition_risk", "status_truth_risk"):
        if candidate[gate] not in GATE_RESULTS:
            raise ContractError(f"{gate} is invalid")
    if candidate["machine_disposition"] == "stage" and any(
        candidate[gate] != "pass"
        for gate in ("disclosure_risk", "repetition_risk", "status_truth_risk")
    ):
        raise ContractError(
            "stage disposition requires all deterministic gates to pass"
        )
    return dict(candidate)


def validate_daily_batch(value: Any) -> dict[str, Any]:
    batch = _mapping(value, "daily batch")
    required = {
        "schema_version", "batch_id", "profile_id", "batch_date",
        "target_count", "floor_count", "ceiling_count", "inventory_status",
        "candidate_ids", "source_tier_counts", "diversity_summary",
        "shortage_reasons",
    }
    missing = required - set(batch)
    if missing:
        raise ContractError(f"daily batch missing keys: {sorted(missing)}")
    if batch["schema_version"] != DAILY_BATCH_SCHEMA:
        raise ContractError("unsupported daily batch schema_version")
    _string(batch["batch_id"], "batch_id")
    _string(batch["profile_id"], "profile_id")
    _editorial_date(batch["batch_date"], "batch_date")
    for key in ("target_count", "floor_count", "ceiling_count"):
        count = batch[key]
        if (
            not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
        ):
            raise ContractError(f"{key} must be a non-negative integer")
    if not batch["floor_count"] <= batch["target_count"] <= batch["ceiling_count"]:
        raise ContractError(
            "daily batch counts must satisfy floor <= target <= ceiling"
        )
    if batch["inventory_status"] not in INVENTORY_STATUSES:
        raise ContractError("inventory_status is invalid")
    ids = _editorial_strings(
        batch["candidate_ids"],
        "candidate_ids",
        allow_empty=True,
    )
    if len(ids) != len(set(ids)) or len(ids) > batch["ceiling_count"]:
        raise ContractError(
            "candidate_ids must be unique and within ceiling_count"
        )
    if (
        batch["inventory_status"] == "HEALTHY"
        and len(ids) < batch["floor_count"]
    ):
        raise ContractError("HEALTHY batch must reach floor_count")
    if (
        batch["inventory_status"] == "DEGRADED_INVENTORY"
        and len(ids) >= batch["floor_count"]
    ):
        raise ContractError(
            "DEGRADED_INVENTORY is only valid below floor_count"
        )
    tiers = _mapping(batch["source_tier_counts"], "source_tier_counts")
    if any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        for value in tiers.values()
    ):
        raise ContractError(
            "source_tier_counts values must be non-negative integers"
        )
    _mapping(batch["diversity_summary"], "diversity_summary")
    _editorial_strings(
        batch["shortage_reasons"],
        "shortage_reasons",
        allow_empty=True,
    )
    return dict(batch)


def validate_policy_identity(value: Any) -> dict[str, str]:
    policy = _mapping(value, "policy identity")
    required = {
        "authority", "source_ref", "source_revision", "content_sha256",
    }
    missing = required - set(policy)
    if missing:
        raise ContractError(f"policy identity missing keys: {sorted(missing)}")
    authority = _string(policy["authority"], "policy.authority")
    source_ref = _string(policy["source_ref"], "policy.source_ref")
    revision = _string(policy["source_revision"], "policy.source_revision")
    if revision.lower() in {"latest", "head", "main", "master", "current"}:
        raise ContractError(
            "policy source_revision must be immutable, not a moving ref"
        )
    digest = _string(
        policy["content_sha256"],
        "policy.content_sha256",
    ).lower()
    if not _EDITORIAL_HEX_64.fullmatch(digest):
        raise ContractError(
            "policy content_sha256 must be a lowercase SHA-256 digest"
        )
    return {
        "authority": authority,
        "source_ref": source_ref,
        "source_revision": revision,
        "content_sha256": digest,
    }


@_editorial_dataclass(frozen=True)
class ActivityEvidence:
    evidence_id: str
    source_kind: str
    source_ref: str
    observed_at: str
    event_at: str
    status: str
    title: str
    summary: str
    repository_ref: str
    visibility: str
    public_eligibility: str
    artifact_refs: tuple[str, ...] = ()
    source_metadata: Mapping[str, Any] = _editorial_field(default_factory=dict)
    schema_version: str = ACTIVITY_EVIDENCE_SCHEMA

    @classmethod
    def from_mapping(cls, value: Any) -> "ActivityEvidence":
        payload = validate_activity_evidence(value)
        return cls(
            evidence_id=payload["evidence_id"],
            source_kind=payload["source_kind"],
            source_ref=payload["source_ref"],
            observed_at=payload["observed_at"],
            event_at=payload["event_at"],
            status=payload["status"],
            title=payload["title"],
            summary=payload["summary"],
            repository_ref=payload["repository_ref"],
            visibility=payload["visibility"],
            public_eligibility=payload["public_eligibility"],
            artifact_refs=tuple(payload["artifact_refs"]),
            source_metadata=dict(payload.get("source_metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "observed_at": self.observed_at,
            "event_at": self.event_at,
            "status": self.status,
            "title": self.title,
            "summary": self.summary,
            "repository_ref": self.repository_ref,
            "visibility": self.visibility,
            "public_eligibility": self.public_eligibility,
            "artifact_refs": list(self.artifact_refs),
            "source_metadata": dict(self.source_metadata),
        }


@_editorial_dataclass(frozen=True)
class StoryCluster:
    story_id: str
    evidence_refs: tuple[str, ...]
    cluster_kind: str
    working_summary: str
    freshness_class: str
    repository_refs: tuple[str, ...]
    public_eligibility: str
    related_context_refs: tuple[str, ...] = ()
    measured_results: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    status_language_constraints: tuple[str, ...] = ()
    schema_version: str = STORY_CLUSTER_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "story_id": self.story_id,
            "evidence_refs": list(self.evidence_refs),
            "cluster_kind": self.cluster_kind,
            "working_summary": self.working_summary,
            "freshness_class": self.freshness_class,
            "repository_refs": list(self.repository_refs),
            "public_eligibility": self.public_eligibility,
            "related_context_refs": list(self.related_context_refs),
            "measured_results": list(self.measured_results),
            "open_questions": list(self.open_questions),
            "status_language_constraints": list(self.status_language_constraints),
        }


@_editorial_dataclass(frozen=True)
class AngleCard:
    angle_id: str
    story_id: str
    angle_type: str
    claim: str
    tension_or_hook: str
    transferable_lesson: str
    evidence_refs: tuple[str, ...]
    audience: tuple[str, ...]
    career_signals: tuple[str, ...]
    why_interesting: str
    risk_class: str
    proof_object_refs: tuple[str, ...] = ()
    required_status_wording: tuple[str, ...] = ()
    counterpoint: str | None = None
    expiry_hint: str | None = None
    schema_version: str = ANGLE_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "angle_id": self.angle_id,
            "story_id": self.story_id,
            "angle_type": self.angle_type,
            "claim": self.claim,
            "tension_or_hook": self.tension_or_hook,
            "transferable_lesson": self.transferable_lesson,
            "evidence_refs": list(self.evidence_refs),
            "audience": list(self.audience),
            "career_signals": list(self.career_signals),
            "why_interesting": self.why_interesting,
            "risk_class": self.risk_class,
            "proof_object_refs": list(self.proof_object_refs),
            "required_status_wording": list(self.required_status_wording),
            "counterpoint": self.counterpoint,
            "expiry_hint": self.expiry_hint,
        }


@_editorial_dataclass(frozen=True)
class DevCandidate:
    payload: Mapping[str, Any]

    @classmethod
    def from_mapping(
        cls,
        value: Any,
        profile: Mapping[str, Any],
    ) -> "DevCandidate":
        return cls(validate_dev_candidate(value, profile))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@_editorial_dataclass(frozen=True)
class DailyBatch:
    payload: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, value: Any) -> "DailyBatch":
        return cls(validate_daily_batch(value))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@_editorial_dataclass(frozen=True)
class PolicyIdentity:
    authority: str
    source_ref: str
    source_revision: str
    content_sha256: str

    @classmethod
    def from_mapping(cls, value: Any) -> "PolicyIdentity":
        return cls(**validate_policy_identity(value))

    def to_dict(self) -> dict[str, str]:
        return {
            "authority": self.authority,
            "source_ref": self.source_ref,
            "source_revision": self.source_revision,
            "content_sha256": self.content_sha256,
        }


@_editorial_dataclass(frozen=True)
class EditorialRunBundle:
    run_id: str
    profile_id: str
    started_at: str
    finished_at: str
    policy: Mapping[str, Any]
    retrieval: Mapping[str, Any]
    evidence: Mapping[str, Any]
    stories: tuple[Mapping[str, Any], ...]
    angles: tuple[Mapping[str, Any], ...]
    candidates: tuple[Mapping[str, Any], ...]
    batch: Mapping[str, Any] | None
    provider_runs: tuple[Mapping[str, Any], ...]
    errors: tuple[Mapping[str, Any], ...]
    status: str
    schema_version: str = RUN_BUNDLE_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "profile_id": self.profile_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "policy": dict(self.policy),
            "retrieval": dict(self.retrieval),
            "evidence": dict(self.evidence),
            "stories": [dict(item) for item in self.stories],
            "angles": [dict(item) for item in self.angles],
            "candidates": [dict(item) for item in self.candidates],
            "batch": dict(self.batch) if self.batch is not None else None,
            "provider_runs": [dict(item) for item in self.provider_runs],
            "errors": [dict(item) for item in self.errors],
            "status": self.status,
        }

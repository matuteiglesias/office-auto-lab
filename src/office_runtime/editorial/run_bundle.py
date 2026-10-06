from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import (
    RUN_BUNDLE_SCHEMA,
    RUN_STATUSES,
    ActivityEvidence,
    AngleCard,
    ContractError,
    DailyBatch,
    EditorialRunBundle,
    PolicyIdentity,
    StoryCluster,
    validate_activity_evidence,
    validate_angle,
    validate_daily_batch,
    validate_dev_candidate,
    validate_policy_identity,
    validate_story_cluster,
)

_SECRET_KEYS = re.compile(
    r"(?:^|_)(?:access_token|refresh_token|api_key|authorization|password|private_key|client_secret|credential)(?:$|_)",
    re.I,
)
_SECRET_VALUES = re.compile(
    r"(?:github_pat_[A-Za-z0-9_]{12,}|gh[pousr]_[A-Za-z0-9]{12,}|sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.I,
)
_LOCAL_PATHS = re.compile(
    r"(?:^|[\s:=\"'])(?:/home/|/Users/|/private/var/|/var/folders/|/mnt/[^\s/]+/|[A-Za-z]:\\|file:///)"
)


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    plain = _plain(value)
    assert_governed_serialization_safe(plain)
    try:
        return (
            json.dumps(
                plain,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError("run bundle contains non-canonical JSON material") from exc


def stable_run_id(
    profile_id: str,
    policy: PolicyIdentity | Mapping[str, Any],
    retrieval: Mapping[str, Any],
) -> str:
    policy_dict = _plain(policy)
    validate_policy_identity(policy_dict)
    identity = {
        "profile_id": profile_id,
        "policy": policy_dict,
        "retrieval_request": {
            "intended_sources": sorted(retrieval.get("intended_sources", [])),
            "time_windows": retrieval.get("time_windows", []),
        },
    }
    digest = hashlib.sha256(
        json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return f"editorial-run:{digest[:24]}"


def build_run_bundle(
    *,
    profile_id: str,
    started_at: str,
    finished_at: str,
    policy: PolicyIdentity,
    retrieval: Mapping[str, Any],
    evidence: Sequence[ActivityEvidence] = (),
    stories: Sequence[StoryCluster] = (),
    angles: Sequence[AngleCard] = (),
    candidates: Sequence[Mapping[str, Any]] = (),
    batch: DailyBatch | Mapping[str, Any] | None = None,
    provider_runs: Sequence[Mapping[str, Any]] = (),
    errors: Sequence[Mapping[str, Any]] = (),
    status: str = "RETRIEVAL_ONLY",
) -> EditorialRunBundle:
    evidence_items = [item.to_dict() for item in evidence]
    story_items = [item.to_dict() for item in stories]
    edges = [
        {
            "story_id": story.story_id,
            "evidence_id": ref,
            "kind": "supported_by",
        }
        for story in stories
        for ref in story.evidence_refs
    ]
    payload = {
        "schema_version": RUN_BUNDLE_SCHEMA,
        "run_id": stable_run_id(profile_id, policy, retrieval),
        "profile_id": profile_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "policy": policy.to_dict(),
        "retrieval": _plain(retrieval),
        "evidence": {"items": evidence_items, "edges": edges},
        "stories": story_items,
        "angles": [item.to_dict() for item in angles],
        "candidates": [_plain(item) for item in candidates],
        "batch": None if batch is None else _plain(batch),
        "provider_runs": [_plain(item) for item in provider_runs],
        "errors": [_plain(item) for item in errors],
        "status": status,
    }
    valid = validate_run_bundle(payload)
    return EditorialRunBundle(
        run_id=valid["run_id"],
        profile_id=valid["profile_id"],
        started_at=valid["started_at"],
        finished_at=valid["finished_at"],
        policy=valid["policy"],
        retrieval=valid["retrieval"],
        evidence=valid["evidence"],
        stories=tuple(valid["stories"]),
        angles=tuple(valid["angles"]),
        candidates=tuple(valid["candidates"]),
        batch=valid["batch"],
        provider_runs=tuple(valid["provider_runs"]),
        errors=tuple(valid["errors"]),
        status=valid["status"],
    )


def validate_run_bundle(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("run bundle must be an object")
    bundle = dict(value)
    required = {
        "schema_version",
        "run_id",
        "profile_id",
        "started_at",
        "finished_at",
        "policy",
        "retrieval",
        "evidence",
        "stories",
        "angles",
        "candidates",
        "batch",
        "provider_runs",
        "errors",
        "status",
    }
    missing = required - set(bundle)
    if missing:
        raise ContractError(f"run bundle missing keys: {sorted(missing)}")
    if bundle["schema_version"] != RUN_BUNDLE_SCHEMA:
        raise ContractError("unsupported run bundle schema_version")
    if bundle["status"] not in RUN_STATUSES:
        raise ContractError("run bundle status is invalid")

    policy = validate_policy_identity(bundle["policy"])
    retrieval = bundle["retrieval"]
    if not isinstance(retrieval, Mapping):
        raise ContractError("run bundle retrieval must be an object")
    expected_run_id = stable_run_id(
        str(bundle["profile_id"]),
        policy,
        retrieval,
    )
    if bundle["run_id"] != expected_run_id:
        raise ContractError(
            "run_id does not match exact profile/policy/retrieval request"
        )
    for key in ("started_at", "finished_at"):
        if not isinstance(bundle[key], str) or not bundle[key]:
            raise ContractError(f"run bundle {key} must be present")

    graph = bundle["evidence"]
    if (
        not isinstance(graph, Mapping)
        or not isinstance(graph.get("items"), list)
        or not isinstance(graph.get("edges"), list)
    ):
        raise ContractError("evidence graph requires items and edges arrays")
    evidence_items = [
        validate_activity_evidence(item)
        for item in graph["items"]
    ]
    evidence_ids = [item["evidence_id"] for item in evidence_items]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ContractError("run bundle evidence IDs must be unique")
    evidence_set = set(evidence_ids)

    stories = [
        validate_story_cluster(item)
        for item in _list(bundle["stories"], "stories")
    ]
    story_by_id = _unique_by(stories, "story_id", "story")
    for story in stories:
        missing_refs = set(story["evidence_refs"]) - evidence_set
        if missing_refs:
            raise ContractError(
                f"story {story['story_id']} references unknown evidence: {sorted(missing_refs)}"
            )

    expected_edges = {
        (story["story_id"], ref, "supported_by")
        for story in stories
        for ref in story["evidence_refs"]
    }
    actual_edges = set()
    for edge in graph["edges"]:
        if not isinstance(edge, Mapping):
            raise ContractError("evidence graph edge must be an object")
        actual_edges.add(
            (
                edge.get("story_id"),
                edge.get("evidence_id"),
                edge.get("kind"),
            )
        )
    if actual_edges != expected_edges:
        raise ContractError(
            "evidence graph edges must exactly match story evidence refs"
        )

    angles = [
        validate_angle(item)
        for item in _list(bundle["angles"], "angles")
    ]
    angle_by_id = _unique_by(angles, "angle_id", "angle")
    for angle in angles:
        story = story_by_id.get(angle["story_id"])
        if story is None or not set(angle["evidence_refs"]).issubset(
            story["evidence_refs"]
        ):
            raise ContractError(
                f"angle {angle['angle_id']} has invalid story/evidence references"
            )

    candidates = _list(bundle["candidates"], "candidates")
    candidate_by_id: dict[str, dict[str, Any]] = {}
    if candidates:
        if bundle["profile_id"] != "dev":
            raise ContractError(
                "W1 run bundle candidate validation is scoped to dev profile"
            )
        profile = {"profile_id": "dev", "strategy": "dev_projection"}
        for raw in candidates:
            candidate = validate_dev_candidate(raw, profile)
            angle = angle_by_id.get(candidate["angle_id"])
            story = story_by_id.get(candidate["story_id"])
            if (
                angle is None
                or story is None
                or angle["story_id"] != story["story_id"]
            ):
                raise ContractError(
                    f"candidate {candidate['candidate_id']} has invalid angle/story references"
                )
            if not set(candidate["evidence_refs"]).issubset(
                story["evidence_refs"]
            ):
                raise ContractError(
                    f"candidate {candidate['candidate_id']} references evidence outside its story"
                )
            if candidate["candidate_id"] in candidate_by_id:
                raise ContractError("candidate IDs must be unique")
            candidate_by_id[candidate["candidate_id"]] = candidate

    batch = bundle["batch"]
    if batch is not None:
        batch = validate_daily_batch(batch)
        staged = {
            candidate_id
            for candidate_id, candidate in candidate_by_id.items()
            if candidate["machine_disposition"] == "stage"
        }
        if set(batch["candidate_ids"]) != staged:
            raise ContractError(
                "batch candidate_ids must exactly equal staged candidates in this run"
            )

    for failure in retrieval.get("failures", []):
        if (
            not isinstance(failure, Mapping)
            or failure.get("status") != "unknown"
        ):
            raise ContractError(
                "retrieval failures must remain explicit unknown state"
            )

    _list(bundle["provider_runs"], "provider_runs")
    _list(bundle["errors"], "errors")
    assert_governed_serialization_safe(bundle)
    return bundle


def atomic_write_run_bundle(
    path: str | Path,
    bundle: EditorialRunBundle | Mapping[str, Any],
) -> Path:
    target = Path(path)
    payload = _plain(bundle)
    validate_run_bundle(payload)
    data = canonical_json_bytes(payload)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        if target.read_bytes() == data:
            return target
        raise ContractError(
            "run bundle path already exists with different immutable content"
        )

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        dir=str(target.parent),
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return target


def assert_governed_serialization_safe(
    value: Any,
    *,
    path: str = "$",
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if _SECRET_KEYS.search(key_text):
                raise ContractError(
                    f"governed evidence cannot serialize credential-like key at {path}.{key_text}"
                )
            assert_governed_serialization_safe(
                item,
                path=f"{path}.{key_text}",
            )
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_governed_serialization_safe(
                item,
                path=f"{path}[{index}]",
            )
    elif isinstance(value, str):
        if _SECRET_VALUES.search(value):
            raise ContractError(
                f"governed evidence cannot serialize secret-like material at {path}"
            )
        if _LOCAL_PATHS.search(value):
            raise ContractError(
                f"governed evidence cannot serialize local absolute paths at {path}"
            )


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(f"run bundle {label} must be an array")
    return value


def _unique_by(
    items: Sequence[Mapping[str, Any]],
    key: str,
    label: str,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in items:
        value = item[key]
        if value in result:
            raise ContractError(f"run bundle {label} IDs must be unique")
        result[value] = item
    return result

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "repo_health.run_bundle.v1"
RUN_STATUSES = frozenset({"success", "partial_success", "error", "empty_success"})


class RunBundleValidationError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_run_bundle(bundle: Mapping[str, Any]) -> None:
    required = {"schema_version", "run", "source", "policy", "intents", "plugin_results", "frontier", "prepared_blocks", "exceptions", "counters"}
    missing = required - set(bundle)
    extra = set(bundle) - required
    if missing or extra:
        raise RunBundleValidationError(f"bundle keys invalid missing={sorted(missing)} extra={sorted(extra)}")
    if bundle["schema_version"] != SCHEMA_VERSION:
        raise RunBundleValidationError("unsupported schema_version")
    run = _mapping(bundle["run"], "run")
    for key in ("run_id", "started_at", "ended_at", "status", "attempt"):
        if key not in run:
            raise RunBundleValidationError(f"run.{key} is required")
    if not str(run["run_id"]).strip() or "/" in str(run["run_id"]) or ".." in str(run["run_id"]):
        raise RunBundleValidationError("run.run_id is unsafe")
    if run["status"] not in RUN_STATUSES:
        raise RunBundleValidationError("run.status is invalid")
    if not isinstance(run["attempt"], int) or run["attempt"] < 1:
        raise RunBundleValidationError("run.attempt must be a positive integer")
    started = _timestamp(run["started_at"], "run.started_at")
    ended = _timestamp(run["ended_at"], "run.ended_at")
    if ended < started:
        raise RunBundleValidationError("run.ended_at precedes run.started_at")
    source = _mapping(bundle["source"], "source")
    if not str(source.get("producer_commit") or "").strip():
        raise RunBundleValidationError("source.producer_commit is required")
    policy = _mapping(bundle["policy"], "policy")
    if not str(policy.get("input_id") or "").strip() or not _sha(policy.get("sha256")):
        raise RunBundleValidationError("policy identity and sha256 are required")

    intents = _rows(bundle["intents"], "intents")
    results = _rows(bundle["plugin_results"], "plugin_results")
    frontier = _rows(bundle["frontier"], "frontier")
    blocks = _rows(bundle["prepared_blocks"], "prepared_blocks")
    exceptions = _rows(bundle["exceptions"], "exceptions")
    intent_ids = _unique_ids(intents, "intent_id", "intents")
    result_ids = _unique_ids(results, "result_id", "plugin_results")
    _unique_ids(blocks, "block_id", "prepared_blocks")
    _unique_ids(exceptions, "exception_id", "exceptions")
    for result in results:
        if result.get("intent_id") not in intent_ids:
            raise RunBundleValidationError(f"plugin result references unknown intent {result.get('intent_id')!r}")
        if result.get("normalized_class") == "system_error" and not result.get("failed"):
            raise RunBundleValidationError("system_error plugin results must set failed=true")
    for row in frontier:
        if row.get("result_id") not in result_ids:
            raise RunBundleValidationError(f"frontier references unknown result {row.get('result_id')!r}")
    for block in blocks:
        links = block.get("source_result_ids")
        if not isinstance(links, list) or not links or any(link not in result_ids for link in links):
            raise RunBundleValidationError(f"prepared block {block.get('block_id')!r} has invalid result linkage")
    for exception in exceptions:
        result_id = exception.get("result_id")
        if result_id is not None and result_id not in result_ids:
            raise RunBundleValidationError(f"exception references unknown result {result_id!r}")
    expected_status = derive_status(results, exceptions)
    if run["status"] != expected_status:
        raise RunBundleValidationError(f"run.status must be {expected_status!r} for bundle contents")
    expected_counts = {
        "intents": len(intents), "plugin_results": len(results), "frontier": len(frontier),
        "prepared_blocks": len(blocks), "exceptions": len(exceptions),
        "failed_plugins": sum(bool(row.get("failed")) for row in results),
    }
    if bundle["counters"] != expected_counts:
        raise RunBundleValidationError(f"counters do not reconcile: expected {expected_counts}")


def derive_status(results: Sequence[Mapping[str, Any]], exceptions: Sequence[Mapping[str, Any]]) -> str:
    if not results and not exceptions:
        return "empty_success"
    failures = sum(bool(row.get("failed")) for row in results) + len(exceptions)
    if failures == 0:
        return "success"
    if results and failures < len(results) + len(exceptions):
        return "partial_success"
    return "error"


def build_run_bundle(*, run_id: str, started_at: str, ended_at: str, attempt: int, producer_commit: str,
                     policy_input_id: str, policy_sha256: str, intents: Sequence[Mapping[str, Any]],
                     plugin_results: Sequence[Mapping[str, Any]], frontier: Sequence[Mapping[str, Any]],
                     prepared_blocks: Sequence[Mapping[str, Any]], exceptions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result_rows = [dict(row) for row in plugin_results]
    exception_rows = [dict(row) for row in exceptions]
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "run": {"run_id": run_id, "started_at": started_at, "ended_at": ended_at, "status": derive_status(result_rows, exception_rows), "attempt": attempt},
        "source": {"producer_commit": producer_commit},
        "policy": {"input_id": policy_input_id, "sha256": policy_sha256},
        "intents": [dict(row) for row in intents], "plugin_results": result_rows,
        "frontier": [dict(row) for row in frontier], "prepared_blocks": [dict(row) for row in prepared_blocks],
        "exceptions": exception_rows,
        "counters": {"intents": len(intents), "plugin_results": len(result_rows), "frontier": len(frontier),
                     "prepared_blocks": len(prepared_blocks), "exceptions": len(exception_rows),
                     "failed_plugins": sum(bool(row.get("failed")) for row in result_rows)},
    }
    validate_run_bundle(bundle)
    return bundle


def schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "spec" / "run_bundle.schema.json"


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RunBundleValidationError(f"{label} must be an object")
    return value


def _rows(value: Any, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise RunBundleValidationError(f"{label} must be an array of objects")
    return value


def _unique_ids(rows: Sequence[Mapping[str, Any]], key: str, label: str) -> set[str]:
    ids = [str(row.get(key) or "") for row in rows]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise RunBundleValidationError(f"{label}.{key} values must be present and unique")
    return set(ids)


def _timestamp(value: Any, label: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise RunBundleValidationError(f"{label} must be ISO-8601") from exc


def _sha(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)

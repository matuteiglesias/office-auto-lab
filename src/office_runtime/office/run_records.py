from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


RUN_RECORD_SCHEMA = "ops.office-run-record.v1"
HEALTH_SCHEMA = "ops.runtime-health-projection.v2"
RUN_RECORD_OWNER = "fr_0004"
DEFAULT_PRODUCER = "fr_0003"
DEFAULT_ROUTINE = "office-v2-generation"


class RunRecordError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _parse_iso(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RunRecordError("timestamp is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RunRecordError(f"invalid timestamp {value!r}") from exc
    if dt.tzinfo is None:
        raise RunRecordError("timestamps must be timezone-aware")
    return dt.astimezone(timezone.utc)


def build_run_record(
    *,
    run_id: str,
    trigger: str,
    started_at: str,
    finished_at: str,
    status: str,
    publication_status: str,
    stage_results: dict[str, dict],
    source_snapshot_digest: str = "",
    manifest_digest: str = "",
    counts: dict[str, int] | None = None,
    warnings: list[dict] | None = None,
    failures: list[dict] | None = None,
    producer_front_id: str = DEFAULT_PRODUCER,
    routine: str = DEFAULT_ROUTINE,
    run_path: str = "",
) -> dict:
    status = str(status).strip().upper()
    publication_status = str(publication_status).strip().upper()
    if status not in {"SUCCEEDED", "FAILED"}:
        raise RunRecordError(f"unsupported run status {status!r}")
    if publication_status not in {"PUBLISHED", "SHADOW", "NOT_PUBLISHED"}:
        raise RunRecordError(f"unsupported publication status {publication_status!r}")
    started = _parse_iso(started_at)
    finished = _parse_iso(finished_at)
    if finished < started:
        raise RunRecordError("finished_at cannot precede started_at")
    record = {
        "schema_version": RUN_RECORD_SCHEMA,
        "run_id": str(run_id).strip(),
        "producer_front_id": str(producer_front_id).strip(),
        "routine": str(routine).strip(),
        "trigger": str(trigger or "manual").strip(),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "status": status,
        "publication_status": publication_status,
        "source_snapshot_digest": str(source_snapshot_digest or ""),
        "manifest_digest": str(manifest_digest or ""),
        "stage_results": stage_results,
        "counts": dict(counts or {}),
        "warnings": list(warnings or []),
        "failures": list(failures or []),
        "artifacts": {"run_path": str(run_path or "")},
    }
    if not record["run_id"] or not record["producer_front_id"] or not record["routine"]:
        raise RunRecordError("run_id, producer_front_id and routine are required")
    if status == "FAILED" and not record["failures"]:
        raise RunRecordError("FAILED run records require at least one failure")
    if status == "SUCCEEDED" and publication_status == "PUBLISHED" and not manifest_digest:
        raise RunRecordError("published successful runs require a manifest digest")
    record["record_digest"] = _stable_digest(record)
    return record


def write_run_record(out_root: Path, record: dict) -> Path:
    if str(record.get("schema_version", "")) != RUN_RECORD_SCHEMA:
        raise RunRecordError("unsupported run-record schema")
    run_id = str(record.get("run_id", "")).strip()
    if not run_id or any(part in run_id for part in ("/", "\\", "..")):
        raise RunRecordError("run_id is unsafe for run-record storage")
    path = Path(out_root) / "v2" / "run_records" / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def load_run_records(out_root: Path) -> list[dict]:
    root = Path(out_root) / "v2" / "run_records"
    if not root.exists():
        return []
    records: list[dict] = []
    for path in sorted(root.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RunRecordError(f"unreadable run record: {path}") from exc
        if str(row.get("schema_version", "")) != RUN_RECORD_SCHEMA:
            raise RunRecordError(f"unsupported run-record schema in {path}")
        records.append(row)
    return records


def compile_runtime_health(
    records: Iterable[dict],
    *,
    generated_at: str | None = None,
    expected_producers: dict[str, bool] | None = None,
    stale_after_seconds: int = 14 * 60 * 60,
) -> dict:
    """Compile runtime-health rows from canonical run records.

    Shadow runs are evidence but do not satisfy scheduled-runtime health. Health
    is a derived observation; it never mutates Carry/priority semantics.
    """
    if stale_after_seconds < 0:
        raise RunRecordError("stale_after_seconds must be non-negative")
    now_text = generated_at or _now_iso()
    now = _parse_iso(now_text)
    expected = dict(expected_producers or {DEFAULT_PRODUCER: True})
    by_producer: dict[str, list[dict]] = {}
    for raw in records:
        row = dict(raw)
        if str(row.get("schema_version", "")) != RUN_RECORD_SCHEMA:
            raise RunRecordError("runtime-health compiler received an unsupported run-record schema")
        producer = str(row.get("producer_front_id", "")).strip()
        if not producer:
            raise RunRecordError("run record missing producer_front_id")
        if str(row.get("publication_status", "")).upper() == "SHADOW":
            continue
        by_producer.setdefault(producer, []).append(row)

    rows: list[dict] = []
    for producer in sorted(set(expected).union(by_producer)):
        producer_expected = bool(expected.get(producer, True))
        candidates = by_producer.get(producer, [])
        candidates.sort(key=lambda row: _parse_iso(str(row.get("finished_at", ""))))
        latest = candidates[-1] if candidates else None
        if not producer_expected:
            status = "N/A"
            bucket = "NO_RUNTIME_EXPECTED"
            observed_at = latest.get("finished_at", "") if latest else ""
            diag = "runtime is intentionally not expected"
            evidence = f"office-run-record:{latest.get('run_id')}" if latest else ""
            source_run_id = latest.get("run_id", "") if latest else ""
        elif latest is None:
            status = "UNKNOWN"
            bucket = "OBSERVABILITY_GAP"
            observed_at = ""
            diag = "no non-shadow run record is available"
            evidence = ""
            source_run_id = ""
        else:
            observed_dt = _parse_iso(str(latest.get("finished_at", "")))
            age = max(0.0, (now - observed_dt).total_seconds())
            observed_at = str(latest.get("finished_at", ""))
            evidence = f"office-run-record:{latest.get('run_id')}"
            source_run_id = str(latest.get("run_id", ""))
            if str(latest.get("status", "")).upper() == "FAILED":
                status = "FAIL"
                bucket = "LAST_RUN_FAILED"
                failure = (latest.get("failures") or [{}])[0]
                diag = str(failure.get("message") or failure.get("type") or "last generation failed")
            elif age > stale_after_seconds:
                status = "WARN"
                bucket = "SCHEDULED_RUN_STALE"
                diag = f"last successful run is {int(age)} seconds old"
            else:
                status = "OK"
                bucket = "LAST_SCHEDULED_RUN_OK"
                diag = "last non-shadow generation completed successfully"
        rows.append({
            "front_id": producer,
            "health_status": status,
            "health_bucket": bucket,
            "last_observed_at": observed_at,
            "last_observed_by": RUN_RECORD_OWNER,
            "short_diag": diag,
            "evidence_ref": evidence,
            "source_run_id": source_run_id,
            "generated_at": now_text,
        })

    result = {
        "schema_version": HEALTH_SCHEMA,
        "generated_at": now_text,
        "generated_by": RUN_RECORD_OWNER,
        "rows": rows,
    }
    result["projection_digest"] = _stable_digest(result)
    return result

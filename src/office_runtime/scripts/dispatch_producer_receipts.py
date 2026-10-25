#!/usr/bin/env python3
"""Durable private-GitHub relay: receipt submission is not cloud acknowledgement.

The local ledger advances to confirmed only after an identifiable Actions
relay job finished SUCCESS (its GCP write/dedupe step is mandatory). Failed or
missing jobs are redriven with bounded backoff. Never delete source receipts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO = "matuteiglesias/projects"
WORKFLOW = "producer-office-receipt-relay.yml"
EVENT = "office-producer-receipt-v1"
ALLOWED = frozenset({"producer.local.office-compile", "producer.local.office-evidence-daily"})
FIELDS = frozenset({
    "contract", "run_id", "producer_id", "scheduler_run_id", "trigger",
    "started_at", "finished_at", "stages", "outputs", "result", "evidence_refs", "warnings",
})
MAX_BYTES = 16384
MAX_ATTEMPTS = 4
MIN_VISIBILITY_SECONDS = 20 * 60
CONFIRMATION_LAG_SECONDS = 5 * 60


class DispatchError(ValueError):
    pass


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def moment(value: str | None) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError):
        return None


def safe_receipt(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    if not 0 < len(raw) <= MAX_BYTES:
        raise DispatchError("receipt file missing or oversized")
    obj = json.loads(raw)
    if not isinstance(obj, dict) or set(obj) != FIELDS:
        raise DispatchError("unsupported receipt fields")
    if obj.get("contract") != "evidence:producer-run-receipt@1":
        raise DispatchError("unsupported receipt contract")
    if obj.get("producer_id") not in ALLOWED:
        raise DispatchError("unapproved producer")
    if not isinstance(obj.get("run_id"), str) or not obj["run_id"]:
        raise DispatchError("invalid run identity")
    if not isinstance(obj.get("result"), dict) or not isinstance(obj.get("outputs"), list):
        raise DispatchError("invalid receipt outcome shape")
    text = canonical(obj).lower()
    for field in (
        "/home/", "/users/", "\\users\\", '"command"', '"cwd"', '"environment"',
        '"password"', '"secret"', '"token"', '"transcript"', '"email_body"',
        '"messages"', '"dataset_rows"', '"raw_document"', '"api_key"', '"access_token"',
    ):
        if field in text:
            raise DispatchError("private/local material rejected")
    digest = hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()
    return obj, digest


def gh_json(gh: str, endpoint: str) -> dict:
    proc = subprocess.run(
        [gh, "api", endpoint], text=True, capture_output=True, timeout=45
    )
    if proc.returncode:
        raise DispatchError(f"GitHub relay status lookup failed (exit={proc.returncode})")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise DispatchError("GitHub relay status lookup returned invalid JSON") from exc


def remote_runs(gh: str, *, repo: str = REPO) -> dict[str, dict]:
    """Fetch recent runs only; fail closed rather than assuming absence."""
    found: dict[str, dict] = {}
    for page in range(1, 6):
        url = (
            f"repos/{repo}/actions/workflows/{WORKFLOW}/runs"
            f"?event=repository_dispatch&per_page=100&page={page}"
        )
        runs = gh_json(gh, url).get("workflow_runs", [])
        if not isinstance(runs, list):
            raise DispatchError("GitHub workflow runs response malformed")
        for item in runs:
            title = str(item.get("display_title", ""))
            if not title.startswith("office-receipt:"):
                continue
            digest = title.removeprefix("office-receipt:")
            if len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
                continue
            # Newest first. Retain latest attempt, but never override a prior
            # successful receipt. A confirmed write wins over a later error.
            old = found.get(digest)
            if old is None or (
                item.get("conclusion") == "success"
                and old.get("conclusion") != "success"
            ):
                found[digest] = {
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "conclusion": item.get("conclusion"),
                    "created_at": item.get("created_at"),
                    "url": item.get("html_url"),
                }
        if len(runs) < 100:
            return found
    raise DispatchError("too many unscanned relay runs; refusing blind redrive")


def failed_stage(gh: str, run_id: int, *, repo: str = REPO) -> str:
    """Return a safe stage name (not remote logs or receipt payload)."""
    if not isinstance(run_id, int):
        return "unidentified_stage"
    try:
        jobs = gh_json(gh, f"repos/{repo}/actions/runs/{run_id}/jobs").get("jobs", [])
        for job in jobs:
            for step in job.get("steps", []):
                if step.get("conclusion") == "failure":
                    name = str(step.get("name", ""))[:90]
                    if name in {
                        "Authenticate GitHub private relay to GCP via OIDC",
                        "Validate Office producer receipt and export once",
                        "Install private relay dependencies",
                        "Run actions/checkout@v4",
                    }:
                        return name
                    return "other_failure_stage"
    except (DispatchError, KeyError, TypeError):
        pass
    return "unidentified_stage"


def send(gh: str, receipt: dict, digest: str, *, repo: str = REPO) -> None:
    payload = canonical({
        "event_type": EVENT,
        "client_payload": {"receipt": receipt, "receipt_sha256": digest, "origin": "office-systemd"},
    })
    proc = subprocess.run(
        [gh, "api", f"repos/{repo}/dispatches", "--method", "POST", "--input", "-"],
        input=payload, text=True, capture_output=True, timeout=45,
    )
    if proc.returncode:
        raise DispatchError(f"GitHub metadata relay submission failed (exit={proc.returncode})")


def read_marker(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise DispatchError("invalid local delivery ledger")
    return data


def write_marker(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(canonical(data) + "\n")
    os.replace(tmp, path)


def run(spool: Path, ledger: Path, *, gh: str, dispatch: bool, max_batch: int) -> dict:
    ledger.mkdir(parents=True, exist_ok=True)
    roots = [spool / x for x in sorted(ALLOWED)]
    receipts = sorted(f for directory in roots for f in directory.glob("*.json") if f.is_file())
    summary: dict[str, Any] = dict(
        scanned=len(receipts), submitted=0, confirmed=0, awaiting_remote=0,
        already_confirmed=0, retried=0, failed_remote=0, blocked=0,
        errors=0, mode="repository_dispatch" if dispatch else "dry_run",
        diagnostics=[],
    )
    records: list[tuple[dict, str, Path]] = []
    for path in receipts:
        try:
            obj, digest = safe_receipt(path)
            if obj["producer_id"] != path.parent.name:
                raise DispatchError("producer identity mismatches spool")
            records.append((obj, digest, ledger / (digest + ".json")))
        except (OSError, ValueError):
            summary["errors"] += 1
            summary["diagnostics"].append({"code": "invalid_local_receipt", "producer": path.parent.name})
    if not records:
        return summary

    if not dispatch:
        summary["would_submit"] = sum(
            not m.is_file() for _, _, m in records
        )
        return summary

    try:
        runs = remote_runs(gh)
    except (DispatchError, subprocess.TimeoutExpired):
        summary["errors"] += 1
        summary["diagnostics"].append({"code": "remote_status_lookup_failed"})
        return summary

    now = utcnow()
    for obj, digest, marker_path in records:
        try:
            marker = read_marker(marker_path)
            remote = runs.get(digest)
            attempts = int(marker.get("attempts", 0))
            last_submission = moment(marker.get("submitted_at"))
            # An older failed run must not cause repeated immediate dispatch
            # while a new attempt has been accepted but not yet indexed by API.
            if remote and last_submission:
                remote_created = moment(remote.get("created_at"))
                if remote_created and remote_created < last_submission - timedelta(seconds=5):
                    remote = None
            if marker.get("status") == "confirmed":
                summary["already_confirmed"] += 1
                continue
            if remote and remote.get("status") == "completed" and remote.get("conclusion") == "success":
                write_marker(marker_path, {
                    "contract": "evidence:office-relay-delivery@2", "receipt_sha256": digest,
                    "status": "confirmed", "attempts": max(1, attempts),
                    "remote_run_id": remote["id"], "confirmed_at": now.isoformat(),
                })
                summary["confirmed"] += 1
                continue
            if remote and remote.get("status") != "completed":
                summary["awaiting_remote"] += 1
                continue

            if remote and remote.get("status") == "completed":
                summary["failed_remote"] += 1
                stage = failed_stage(gh, remote["id"])
                summary["diagnostics"].append({
                    "code": "remote_relay_failed", "producer": obj["producer_id"],
                    "digest_prefix": digest[:12], "run_url": remote.get("url"),
                    "failed_step": stage,
                })
                baseline = moment(remote.get("created_at")) or moment(marker.get("submitted_at"))
                # Remote run completed with an error; a bounded automatic retry
                # can succeed after IAM/network fixes without losing evidence.
            else:
                baseline = moment(marker.get("submitted_at"))
                if baseline is not None and (now - baseline).total_seconds() < MIN_VISIBILITY_SECONDS:
                    summary["awaiting_remote"] += 1
                    continue

            # Completed failures get a short backoff; missing events get a
            # longer visibility grace (above) to avoid duplicate dispatches.
            if baseline and (now - baseline).total_seconds() < CONFIRMATION_LAG_SECONDS * max(1, attempts):
                summary["awaiting_remote"] += 1
                continue
            if attempts >= MAX_ATTEMPTS:
                summary["blocked"] += 1
                summary["diagnostics"].append({
                    "code": "retry_budget_exhausted", "producer": obj["producer_id"],
                    "digest_prefix": digest[:12],
                })
                continue
            if summary["submitted"] >= max_batch:
                break
            send(gh, obj, digest)
            write_marker(marker_path, {
                "contract": "evidence:office-relay-delivery@2",
                "receipt_sha256": digest, "status": "submitted",
                "submitted_at": now.isoformat(), "attempts": attempts + 1,
            })
            summary["submitted"] += 1
            if attempts:
                summary["retried"] += 1
        except (OSError, ValueError, subprocess.TimeoutExpired):
            summary["errors"] += 1
            summary["diagnostics"].append({
                "code": "submission_or_ledger_failed", "producer": obj["producer_id"],
                "digest_prefix": digest[:12],
            })
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spool", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--gh", default="gh")
    ap.add_argument("--max-batch", type=int, default=20)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--dispatch", action="store_true")
    a = ap.parse_args()
    if not 1 <= a.max_batch <= 50:
        print("invalid batch bound", file=sys.stderr)
        return 2
    summary = run(a.spool, a.ledger, gh=a.gh, dispatch=a.dispatch, max_batch=a.max_batch)
    print(json.dumps(summary, sort_keys=True))
    return 2 if summary["errors"] or summary["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

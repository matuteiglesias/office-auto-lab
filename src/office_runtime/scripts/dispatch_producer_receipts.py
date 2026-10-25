#!/usr/bin/env python3
"""Deliver immutable metadata-only Office receipts via a private GitHub Actions relay.

GitHub is the transport queue: a successful repository_dispatch records durable
submission, not proof of GCP ingestion. Never remove local source receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = "matuteiglesias/projects"
EVENT = "office-producer-receipt-v1"
ALLOWED = frozenset({"producer.local.office-compile", "producer.local.office-evidence-daily"})
FIELDS = frozenset({
    "contract", "run_id", "producer_id", "scheduler_run_id", "trigger",
    "started_at", "finished_at", "stages", "outputs", "result", "evidence_refs", "warnings",
})
MAX_BYTES = 16384


class DispatchError(ValueError):
    pass


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


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
    # Keep opaque receipt payload only inside the private repository dispatch.
    digest = hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()
    return obj, digest


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
        # Avoid printing GitHub's HTTP error body or request echo.
        raise DispatchError(f"GitHub metadata relay returned exit code {proc.returncode}")


def run(spool: Path, ledger: Path, *, gh: str, dispatch: bool, max_batch: int) -> dict:
    ledger.mkdir(parents=True, exist_ok=True)
    roots = [spool / x for x in sorted(ALLOWED)]
    receipts = sorted(f for directory in roots for f in directory.glob("*.json") if f.is_file())
    sent = 0
    already = 0
    errors = 0
    for path in receipts:
        if sent >= max_batch:
            break
        try:
            obj, digest = safe_receipt(path)
            if obj["producer_id"] != path.parent.name:
                raise DispatchError("producer identity mismatches spool")
            marker = ledger / (digest + ".json")
            if marker.is_file():
                already += 1
                continue
            if dispatch:
                send(gh, obj, digest)
                tmp = marker.with_suffix(".tmp")
                tmp.write_text(canonical({"contract": "evidence:office-dispatch-accepted@1", "receipt_sha256": digest}) + "\n")
                os.replace(tmp, marker)
            sent += 1
        except (OSError, ValueError, subprocess.TimeoutExpired):
            errors += 1
    return {
        "scanned": len(receipts), "submitted" if dispatch else "would_submit": sent,
        "already_submitted": already, "errors": errors,
        "mode": "repository_dispatch" if dispatch else "dry_run",
    }


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
    return 2 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Orchestrate producer-owned Media evidence into a KB Artifacts named selection."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

_SELECTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class CompositionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CompositionRequest:
    selection_id: str
    start: str
    end: str
    topic_pattern: str

    def validate(self) -> None:
        if ".." in self.selection_id or not _SELECTION_ID.fullmatch(self.selection_id):
            raise CompositionError("selection_id is invalid")
        try:
            start = date.fromisoformat(self.start)
            end = date.fromisoformat(self.end)
        except ValueError as exc:
            raise CompositionError("start/end must be ISO dates") from exc
        if start > end:
            raise CompositionError("start must not be after end")
        if not self.topic_pattern.strip():
            raise CompositionError("topic_pattern is required")
        if len(self.topic_pattern) > 512:
            raise CompositionError("topic_pattern is too long")


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise CompositionError(f"missing {label}: {path}")


def _verify_roots(media_root: Path, kb_root: Path, store_root: Path) -> None:
    _require_file(media_root / "SYSTEM.yaml", "Media Monitor SYSTEM.yaml")
    _require_file(media_root / "apps" / "media_watch" / "evidence_export.py", "Media evidence exporter")
    _require_file(kb_root / "SYSTEM.yaml", "KB Artifacts SYSTEM.yaml")
    _require_file(kb_root / "src" / "kb_artifacts" / "cli.py", "KB Artifacts CLI")
    if not store_root.is_dir():
        raise CompositionError(f"missing Media Monitor store: {store_root}")
    media_system = (media_root / "SYSTEM.yaml").read_text(encoding="utf-8")
    kb_system = (kb_root / "SYSTEM.yaml").read_text(encoding="utf-8")
    if "matuteiglesias/media_monitor" not in media_system:
        raise CompositionError("Media Monitor root has unexpected SYSTEM identity")
    if "matuteiglesias/kb-artifacts" not in kb_system:
        raise CompositionError("KB Artifacts root has unexpected SYSTEM identity")


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def _profile_text(evidence_path: Path) -> str:
    escaped = evidence_path.as_posix().replace("\\", "\\\\").replace('"', '\\"')
    return (
        "[corpora.media-monitor]\n"
        'description = "Governed Media Monitor summary evidence"\n'
        f'chunk_globs = ["{escaped}"]\n'
        "excerpts_permitted_by_default = false\n"
        "\n"
        "[corpora.media-monitor.annotations]\n"
        'producer = "media-monitor"\n'
    )


def compose_media_selection(
    *,
    request: CompositionRequest,
    media_monitor_root: Path,
    media_store_root: Path,
    kb_artifacts_root: Path,
    work_root: Path,
    apply: bool = False,
) -> dict[str, Any]:
    request.validate()
    media_root = media_monitor_root.resolve()
    store_root = media_store_root.resolve()
    kb_root = kb_artifacts_root.resolve()
    work_root = work_root.resolve()
    _verify_roots(media_root, kb_root, store_root)

    run_root = kb_root / "artifacts" / "runs" / request.selection_id
    if run_root.exists():
        raise CompositionError(f"selection output already exists: {request.selection_id}")

    work_dir = work_root / request.selection_id
    evidence = work_dir / "media.evidence.jsonl"
    profiles = work_dir / "corpora.toml"

    media_command = [
        sys.executable, "-m", "apps.media_watch.evidence_export",
        "--store-root", str(store_root),
        "--output", str(evidence),
    ]
    select_command = [
        sys.executable, "-m", "kb_artifacts.cli", "select",
        "--corpus", "media-monitor",
        "--profiles-file", str(profiles),
        "--from", request.start,
        "--to", request.end,
        "--text", request.topic_pattern,
        "--group-by", "source_id",
        "--output", str(run_root),
    ]

    plan = {
        "contract": "ops.media-evidence-composition-plan@1",
        "selection_id": request.selection_id,
        "selection": {
            "from": request.start,
            "to": request.end,
            "topic_pattern": request.topic_pattern,
            "corpus": "media-monitor",
        },
        "apply": apply,
        "commands": {
            "media_export": media_command,
            "kb_select": select_command,
        },
        "handoff": {
            "mctx_command": f"mctx evidence {request.selection_id}",
            "mctx_uri": f"matias-context://selected/kb-artifacts/{request.selection_id}",
        },
    }
    if not apply:
        return plan

    work_dir.mkdir(parents=True, exist_ok=False)
    profiles.write_text(_profile_text(evidence), encoding="utf-8")

    media_env = dict(os.environ)
    media_env["PYTHONPATH"] = str(media_root)
    exported = _run(media_command, cwd=media_root, env=media_env)
    if exported.returncode != 0:
        raise CompositionError("Media evidence export failed: " + (exported.stderr.strip() or exported.stdout.strip()))
    try:
        export_receipt = json.loads(exported.stdout)
    except json.JSONDecodeError as exc:
        raise CompositionError("Media evidence exporter returned invalid JSON") from exc

    kb_env = dict(os.environ)
    kb_env["PYTHONPATH"] = str(kb_root / "src")
    selected = _run(select_command, cwd=kb_root, env=kb_env)
    if selected.returncode != 0:
        raise CompositionError("KB Artifacts selection failed: " + (selected.stderr.strip() or selected.stdout.strip()))

    manifest_path = run_root / "manifest.json"
    _require_file(manifest_path, "selection manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("counts", {}).get("selected", 0) < 1:
        raise CompositionError("selection unexpectedly contains no records")
    checksum = manifest.get("output_checksums", {}).get("selected.jsonl")
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise CompositionError("selection manifest did not bind selected.jsonl")

    return {
        **plan,
        "contract": "ops.media-evidence-composition-receipt@1",
        "status": "selected",
        "producer_adapter_contract": export_receipt.get("contract"),
        "producer_records": export_receipt.get("records"),
        "selected_count": manifest["counts"]["selected"],
        "selected_sha256": checksum,
    }

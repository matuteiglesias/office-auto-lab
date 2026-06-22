from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from office_runtime.capture import CAPTURE_LIFECYCLE_EVENTS

RAW_FEEDBACK_DIR = "human_feedback"
PROCESSING_DIR = "capture_processing"
REINGEST_DIR = "reingest_candidates"

_STATUS_BY_STAGE = {
    "capture.created": "pending_transcription",
    "capture.transcribed": "transcribed",
    "capture.routed": "routed",
    "capture.artifact_candidate.created": "artifact_candidate",
    "capture.reingest_candidate.created": "pending_reingest",
    "capture.approved": "approved",
    "capture.applied": "applied",
}
_STATUS_ORDER = [
    "pending_transcription",
    "transcribed",
    "routed",
    "artifact_candidate",
    "pending_reingest",
    "approved",
    "applied",
    "archived",
    "malformed",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any] | None, str | None]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                yield line_no, None, f"invalid json: {exc.msg}"
                continue
            if not isinstance(value, dict):
                yield line_no, None, "jsonl record is not an object"
                continue
            yield line_no, value, None


def _iter_jsonl_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.jsonl") if p.is_file())


def _first(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _target_from(row: dict[str, Any]) -> dict[str, str]:
    return {
        "project_id": _first(row, "project_id", "target_project_id"),
        "title": _first(row, "project_title", "title", "target_title", "row_title"),
        "queue_key": _first(row, "queue_key", "queue", "selected_from"),
    }


def _audio_from(row: dict[str, Any]) -> dict[str, str]:
    return {"rel_path": _first(row, "audio_path", "audio_rel_path", "audio")}


def _event_id_for(row: dict[str, Any], derived: bool) -> str:
    if derived:
        return _first(row, "source_event_id", "event_id")
    return _first(row, "event_id", "source_event_id")


def _stage_for(row: dict[str, Any], default: str) -> str:
    return _first(row, "event_type", "stage", "event", "type", "kind") or default


def _timestamp_for(row: dict[str, Any]) -> str:
    return _first(row, "ts", "timestamp", "created_at", "updated_at")


def _timeline_event(
    row: dict[str, Any],
    *,
    stage: str,
    source_path: Path,
    line_no: int,
    root: Path,
) -> dict[str, Any]:
    event = {
        "stage": stage,
        "ts": _timestamp_for(row),
        "status": _first(row, "status") or "ok",
        "source_path": str(source_path.relative_to(root.parent) if source_path.is_relative_to(root.parent) else source_path),
        "source_line": line_no,
    }
    for key in (
        "transcript",
        "transcript_text",
        "model",
        "route",
        "routing",
        "candidate_id",
        "candidate_type",
        "candidate_ref",
        "artifact_path",
        "reingest_candidate_id",
        "summary",
        "review_note",
    ):
        if key in row:
            event[key] = row[key]
    return event


def _empty_capture(event_id: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "created_at": "",
        "status": "pending_transcription",
        "target": {"project_id": "", "title": "", "queue_key": ""},
        "audio": {"rel_path": ""},
        "human_note": "",
        "row_snapshot": {},
        "transcript": {"status": "absent", "text": "", "model": ""},
        "routing": None,
        "artifact_candidate": None,
        "reingest_candidate": None,
        "approval": {"status": "not_requested"},
        "events": [],
        "timeline": [],
        "warnings": [],
    }


def _apply_raw(capture: dict[str, Any], row: dict[str, Any]) -> None:
    capture["created_at"] = capture["created_at"] or _timestamp_for(row)
    target = _target_from(row)
    for key, value in target.items():
        if value and not capture["target"].get(key):
            capture["target"][key] = value
    audio = _audio_from(row)
    if audio["rel_path"] and not capture["audio"].get("rel_path"):
        capture["audio"] = audio
    capture["human_note"] = capture["human_note"] or _first(row, "human_note", "note", "text")
    if isinstance(row.get("row_snapshot"), dict) and not capture.get("row_snapshot"):
        capture["row_snapshot"] = row["row_snapshot"]


def _apply_derived(capture: dict[str, Any], row: dict[str, Any], stage: str) -> None:
    target = _target_from(row)
    for key, value in target.items():
        if value and not capture["target"].get(key):
            capture["target"][key] = value

    if stage == "capture.transcribed":
        transcript = row.get("transcript") if isinstance(row.get("transcript"), dict) else {}
        capture["transcript"] = {
            "status": _first(row, "status") or "ok",
            "text": _first(transcript, "text") or _first(row, "transcript", "transcript_text", "text"),
            "model": _first(transcript, "model") or _first(row, "model"),
        }
    elif stage == "capture.routed":
        routing = row.get("routing") if isinstance(row.get("routing"), dict) else {}
        capture["routing"] = {
            "status": _first(row, "status") or "ok",
            "route": _first(routing, "artifact_type") or _first(row, "route", "candidate_type"),
            "capture_mode": _first(routing, "capture_mode"),
            "lane": _first(routing, "lane"),
            "artifact_type": _first(routing, "artifact_type"),
            "routing_sentence": _first(routing, "routing_sentence"),
            "confidence": _first(routing, "confidence"),
            "rationale": _first(row, "rationale", "summary"),
        }
    elif stage == "capture.artifact_candidate.created":
        candidate = row.get("artifact_candidate") if isinstance(row.get("artifact_candidate"), dict) else {}
        capture["artifact_candidate"] = {
            "status": _first(row, "status") or "candidate",
            "candidate_id": _first(row, "candidate_id"),
            "candidate_type": _first(candidate, "type") or _first(row, "candidate_type"),
            "artifact_path": _first(row, "artifact_path", "candidate_ref"),
            "summary": _first(candidate, "text") or _first(row, "summary"),
            "text": _first(candidate, "text"),
            "confidence": _first(candidate, "confidence"),
            "evidence_excerpt": _first(candidate, "evidence_excerpt"),
        }
    elif stage == "capture.reingest_candidate.created":
        candidate = row.get("reingest_candidate") if isinstance(row.get("reingest_candidate"), dict) else {}
        capture["reingest_candidate"] = {
            "status": _first(row, "status") or "proposed",
            "reingest_candidate_id": _first(row, "reingest_candidate_id", "candidate_id"),
            "candidate_type": _first(row, "candidate_type"),
            "candidate_ref": _first(row, "candidate_ref", "artifact_path"),
            "summary": _first(row, "summary") or _first(candidate, "target_surface"),
            "target_surface": _first(candidate, "target_surface"),
            "target_id": _first(candidate, "target_id"),
            "proposed_delta": candidate.get("proposed_delta", {}) if isinstance(candidate.get("proposed_delta"), dict) else {},
            "requires_human_approval": bool(candidate.get("requires_human_approval", True)),
        }
    elif stage in {"capture.approved", "capture.applied"}:
        capture["approval"] = {
            "status": "applied" if stage == "capture.applied" else "approved",
            "review_note": _first(row, "review_note", "summary"),
        }


def _finalize_capture(capture: dict[str, Any]) -> None:
    capture["timeline"].sort(key=lambda e: (e.get("ts") or "", e.get("source_path") or "", e.get("source_line") or 0))
    capture["events"] = [e["stage"] for e in capture["timeline"]]
    known = [e["stage"] for e in capture["timeline"] if e.get("stage") in _STATUS_BY_STAGE]
    if known:
        capture["status"] = _STATUS_BY_STAGE[known[-1]]
    if any(e.get("stage") == "capture.archived" for e in capture["timeline"]):
        capture["status"] = "archived"
    if capture["timeline"] and not capture["created_at"]:
        capture["created_at"] = capture["timeline"][0].get("ts", "")


def compile_lifecycle(
    inbox_root: Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    inbox_root = Path(inbox_root)
    generated_at = generated_at or utc_now()
    captures: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, Any]] = []

    raw_root = inbox_root / RAW_FEEDBACK_DIR
    for path in _iter_jsonl_files(raw_root):
        for line_no, row, error in _read_jsonl(path):
            if error:
                warnings.append({"source_path": str(path), "source_line": line_no, "message": error})
                continue
            assert row is not None
            event_id = _event_id_for(row, derived=False)
            if not event_id:
                warnings.append({"source_path": str(path), "source_line": line_no, "message": "missing event_id"})
                continue
            capture = captures.setdefault(event_id, _empty_capture(event_id))
            _apply_raw(capture, row)
            capture["timeline"].append(_timeline_event(row, stage="capture.created", source_path=path, line_no=line_no, root=inbox_root))

    for dirname, default_stage in (
        (PROCESSING_DIR, "capture.processing"),
        (REINGEST_DIR, "capture.reingest_candidate.created"),
    ):
        stream_root = inbox_root / dirname
        for path in _iter_jsonl_files(stream_root):
            for line_no, row, error in _read_jsonl(path):
                if error:
                    warnings.append({"source_path": str(path), "source_line": line_no, "message": error})
                    continue
                assert row is not None
                event_id = _event_id_for(row, derived=True)
                if not event_id:
                    warnings.append({"source_path": str(path), "source_line": line_no, "message": "missing source_event_id"})
                    continue
                stage = _stage_for(row, default_stage)
                capture = captures.setdefault(event_id, _empty_capture(event_id))
                _apply_derived(capture, row, stage)
                capture["timeline"].append(_timeline_event(row, stage=stage, source_path=path, line_no=line_no, root=inbox_root))

    for capture in captures.values():
        _finalize_capture(capture)

    ordered_captures = sorted(captures.values(), key=lambda c: (c.get("created_at") or "", c.get("event_id") or ""))
    counts = Counter(c["status"] for c in ordered_captures)
    status_counts = {status: int(counts.get(status, 0)) for status in _STATUS_ORDER}

    return {
        "generated_at": generated_at,
        "source": "office-auto-lab",
        "source_roots": {
            "raw_feedback": str(raw_root),
            "processing_events": str(inbox_root / PROCESSING_DIR),
            "reingest_candidates": str(inbox_root / REINGEST_DIR),
        },
        "status_counts": status_counts,
        "captures": ordered_captures,
        "warnings": warnings,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_markdown(lifecycle: dict[str, Any]) -> str:
    lines = [
        "# Capture Lifecycle",
        "",
        f"- Generated at: `{lifecycle.get('generated_at', '')}`",
        f"- Source: `{lifecycle.get('source', '')}`",
        f"- Captures: {len(lifecycle.get('captures', []))}",
        f"- Warnings: {len(lifecycle.get('warnings', []))}",
        "",
        "## Status counts",
        "",
    ]
    counts = lifecycle.get("status_counts", {}) or {}
    for status in _STATUS_ORDER:
        lines.append(f"- {status}: {counts.get(status, 0)}")
    lines += ["", "## Captures", ""]
    for capture in lifecycle.get("captures", []):
        target = capture.get("target", {}) or {}
        transcript = capture.get("transcript", {}) or {}
        lines += [
            f"### {capture.get('event_id', '')}",
            "",
            f"- Status: `{capture.get('status', '')}`",
            f"- Project: `{target.get('project_id', '')}` {target.get('title', '')}".rstrip(),
            f"- Queue: `{target.get('queue_key', '')}`",
            f"- Audio: `{(capture.get('audio', {}) or {}).get('rel_path', '')}`",
            f"- Transcript status: `{transcript.get('status', 'absent')}`",
            f"- Events: {', '.join(capture.get('events', []))}",
            "",
        ]
        if transcript.get("text"):
            lines += ["> " + str(transcript.get("text", "")).replace("\n", " "), ""]
    if lifecycle.get("warnings"):
        lines += ["## Warnings", ""]
        for warning in lifecycle["warnings"]:
            lines.append(f"- {warning.get('source_path')}:{warning.get('source_line')} — {warning.get('message')}")
        lines.append("")
    return "\n".join(lines)


def write_markdown(path: Path, lifecycle: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(lifecycle), encoding="utf-8")


def write_csv(path: Path, lifecycle: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "event_id",
        "created_at",
        "status",
        "project_id",
        "project_title",
        "queue_key",
        "audio_rel_path",
        "transcript_status",
        "routing_status",
        "artifact_candidate_status",
        "reingest_candidate_status",
        "approval_status",
        "events",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for capture in lifecycle.get("captures", []):
            target = capture.get("target", {}) or {}
            writer.writerow({
                "event_id": capture.get("event_id", ""),
                "created_at": capture.get("created_at", ""),
                "status": capture.get("status", ""),
                "project_id": target.get("project_id", ""),
                "project_title": target.get("title", ""),
                "queue_key": target.get("queue_key", ""),
                "audio_rel_path": (capture.get("audio", {}) or {}).get("rel_path", ""),
                "transcript_status": (capture.get("transcript", {}) or {}).get("status", ""),
                "routing_status": (capture.get("routing") or {}).get("status", "absent"),
                "artifact_candidate_status": (capture.get("artifact_candidate") or {}).get("status", "absent"),
                "reingest_candidate_status": (capture.get("reingest_candidate") or {}).get("status", "absent"),
                "approval_status": (capture.get("approval") or {}).get("status", ""),
                "events": "|".join(capture.get("events", [])),
            })


def _is_work_block_candidate(capture: dict[str, Any]) -> bool:
    artifact = capture.get("artifact_candidate") or {}
    reingest = capture.get("reingest_candidate") or {}
    typed_values = {
        str(artifact.get("candidate_type") or "").strip().lower(),
        str(artifact.get("type") or "").strip().lower(),
        str(reingest.get("candidate_type") or "").strip().lower(),
        str(reingest.get("target_surface") or "").strip().lower(),
    }
    return "work_block_candidate_stub" in typed_values or "block_candidate_stub" in typed_values


def compile_capture_candidates(lifecycle: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for capture in lifecycle.get("captures", []):
        if not _is_work_block_candidate(capture):
            continue
        target = capture.get("target") or {}
        artifact = capture.get("artifact_candidate") or {}
        reingest = capture.get("reingest_candidate") or {}
        source_event_id = str(capture.get("event_id") or "")
        text = str(artifact.get("text") or artifact.get("summary") or "")
        evidence = str(artifact.get("evidence_excerpt") or "")
        proposed_delta = reingest.get("proposed_delta") if isinstance(reingest.get("proposed_delta"), dict) else {}
        row = {
            "source_event_id": source_event_id,
            "candidate_id": f"capture_{source_event_id}_work_block_candidate_stub",
            "candidate_type": "work_block_candidate_stub",
            "status": "candidate",
            "review_required": "true",
            "project_id": str(target.get("project_id") or reingest.get("target_id") or ""),
            "title": str(target.get("title") or ""),
            "queue_key": str(target.get("queue_key") or ""),
            "target_surface": str(reingest.get("target_surface") or ""),
            "target_id": str(reingest.get("target_id") or ""),
            "text": text,
            "next": str(proposed_delta.get("next") or text),
            "needs": str(proposed_delta.get("needs") or "Execution review"),
            "evidence_excerpt": evidence,
            "created_at": str(capture.get("created_at") or ""),
        }
        candidates.append(row)
    candidates.sort(key=lambda r: (r.get("created_at", ""), r.get("source_event_id", ""), r.get("candidate_id", "")))
    return {"generated_at": lifecycle.get("generated_at", ""), "status": "ok", "candidates": candidates}


def render_capture_candidates_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Capture Candidates",
        "",
        f"- Generated at: `{data.get('generated_at', '')}`",
        f"- Candidates: {len(data.get('candidates', []))}",
        "",
    ]
    for row in data.get("candidates", []):
        lines += [
            f"## {row.get('source_event_id', '')}",
            "",
            f"- Status: `{row.get('status', '')}` / review-required: `{row.get('review_required', '')}`",
            f"- Project: `{row.get('project_id', '')}` {row.get('title', '')}".rstrip(),
            f"- Type: `{row.get('candidate_type', '')}`",
            f"- Target: `{row.get('target_surface', '')}` `{row.get('target_id', '')}`".rstrip(),
            f"- Next: {row.get('next', '')}",
        ]
        if row.get("evidence_excerpt"):
            lines += ["", "> " + str(row.get("evidence_excerpt", "")).replace("\n", " ")]
        lines.append("")
    return "\n".join(lines)


def render_block_candidate_stubs_markdown(data: dict[str, Any]) -> str:
    lines = ["# Block Candidate Stubs", "", f"- Candidates: {len(data.get('candidates', []))}", ""]
    for row in data.get("candidates", []):
        lines += [
            f"- `{row.get('source_event_id', '')}` → `{row.get('project_id', '')}`: {row.get('next', '')} "
            f"(review-required: `{row.get('review_required', '')}`)",
        ]
    lines.append("")
    return "\n".join(lines)


def write_capture_candidate_artifacts(lifecycle: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir = Path(out_dir)
    data = compile_capture_candidates(lifecycle)
    candidates_json = out_dir / "capture_candidates.json"
    candidates_md = out_dir / "capture_candidates.md"
    stubs_csv = out_dir / "block_candidate_stubs.csv"
    stubs_md = out_dir / "block_candidate_stubs.md"
    write_json(candidates_json, data)
    candidates_md.write_text(render_capture_candidates_markdown(data), encoding="utf-8")
    fields = [
        "source_event_id",
        "candidate_id",
        "candidate_type",
        "status",
        "review_required",
        "project_id",
        "title",
        "queue_key",
        "target_surface",
        "target_id",
        "text",
        "next",
        "needs",
        "evidence_excerpt",
        "created_at",
    ]
    stubs_csv.parent.mkdir(parents=True, exist_ok=True)
    with stubs_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in data.get("candidates", []):
            writer.writerow({field: row.get(field, "") for field in fields})
    stubs_md.write_text(render_block_candidate_stubs_markdown(data), encoding="utf-8")
    return {
        "capture_candidates_json": str(candidates_json),
        "capture_candidates_markdown": str(candidates_md),
        "block_candidate_stubs_csv": str(stubs_csv),
        "block_candidate_stubs_markdown": str(stubs_md),
    }


def write_lifecycle_artifacts(lifecycle: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir = Path(out_dir)
    json_path = out_dir / "capture_lifecycle.json"
    md_path = out_dir / "capture_lifecycle.md"
    csv_path = out_dir / "capture_lifecycle.csv"
    write_json(json_path, lifecycle)
    write_markdown(md_path, lifecycle)
    write_csv(csv_path, lifecycle)
    outputs = {"json": str(json_path), "markdown": str(md_path), "csv": str(csv_path)}
    outputs.update(write_capture_candidate_artifacts(lifecycle, out_dir))
    return outputs


def compile_and_write(inbox_root: Path, out_dir: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    lifecycle = compile_lifecycle(inbox_root, generated_at=generated_at)
    outputs = write_lifecycle_artifacts(lifecycle, out_dir)
    return {
        "status": "ok",
        "captures": len(lifecycle.get("captures", [])),
        "warnings": len(lifecycle.get("warnings", [])),
        "outputs": outputs,
    }

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from office_runtime.capture.lifecycle import PROCESSING_DIR, compile_lifecycle
from office_runtime.capture.transcription import append_jsonl, transcribe_event

DEFAULT_PROCESSING_MODEL = "gpt-4o-mini"
CAPTURE_MODES = ["Capture", "Re-entry", "Correction", "Question"]
CAPTURE_LANES = ["Projects / Ops", "Personal Ops", "Research", "Inbox", "Unknown"]
ARTIFACT_TYPES = ["Next Pointer", "Work Block Candidate", "Note", "Question", "Other"]
CONFIDENCE_VALUES = ["low", "medium", "high"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return json.loads(json.dumps(value, default=lambda o: getattr(o, "__dict__", str(o))))


def _event_date(capture: dict[str, Any]) -> str:
    stamp = str(capture.get("created_at") or capture.get("event_id") or utc_now())
    if len(stamp) >= 10 and stamp[4] == "-" and stamp[7] == "-":
        return stamp[:10]
    return utc_now()[:10]


def _processing_path(inbox_root: Path, capture: dict[str, Any]) -> Path:
    return inbox_root / PROCESSING_DIR / f"{_event_date(capture)}.jsonl"


def _find_capture(inbox_root: Path, event_id: str) -> dict[str, Any] | None:
    lifecycle = compile_lifecycle(inbox_root)
    for capture in lifecycle.get("captures", []):
        if capture.get("event_id") == event_id:
            return capture
    return None


def _has_stage(capture: dict[str, Any] | None, stage: str) -> bool:
    return bool(capture and stage in (capture.get("events") or []))


def _context(capture: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_event_id": capture.get("event_id", ""),
        "target": capture.get("target") or {},
        "row_snapshot": capture.get("row_snapshot") or capture.get("target") or {},
        "human_note": capture.get("human_note", ""),
        "transcript": capture.get("transcript") or {},
        "routing": capture.get("routing") or {},
        "artifact_candidate": capture.get("artifact_candidate") or {},
        "capture_ontology": {"capture_modes": CAPTURE_MODES, "lanes": CAPTURE_LANES, "artifact_types": ARTIFACT_TYPES},
    }


ROUTING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["capture_mode", "lane", "artifact_type", "routing_sentence", "confidence"],
    "properties": {
        "capture_mode": {"type": "string", "enum": CAPTURE_MODES},
        "lane": {"type": "string", "enum": CAPTURE_LANES},
        "artifact_type": {"type": "string", "enum": ARTIFACT_TYPES},
        "routing_sentence": {"type": "string"},
        "confidence": {"type": "string", "enum": CONFIDENCE_VALUES},
    },
}

ARTIFACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["type", "text", "confidence", "evidence_excerpt"],
    "properties": {
        "type": {"type": "string"},
        "text": {"type": "string"},
        "confidence": {"type": "string", "enum": CONFIDENCE_VALUES},
        "evidence_excerpt": {"type": "string"},
    },
}

REINGEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["target_surface", "target_id", "proposed_delta", "requires_human_approval"],
    "properties": {
        "target_surface": {"type": "string", "enum": ["carry_state", "front_registry", "queue", "none"]},
        "target_id": {"type": "string"},
        "proposed_delta": {"type": "object", "additionalProperties": {"type": "string"}},
        "requires_human_approval": {"type": "boolean"},
    },
}


def _validate_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            return [f"{path} must be object"]
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key} is not allowed")
        additional = schema.get("additionalProperties")
        for key, item in value.items():
            child_schema = properties.get(key) or (additional if isinstance(additional, dict) else None)
            if child_schema:
                errors.extend(_validate_schema(item, child_schema, f"{path}.{key}"))
    elif expected == "string":
        if not isinstance(value, str):
            errors.append(f"{path} must be string")
    elif expected == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path} must be boolean")
    enum = schema.get("enum")
    if enum is not None and value not in enum:
        errors.append(f"{path} must be one of {enum}")
    return errors


def _structured_response(prompt: str, schema: dict[str, Any], *, model: str, client: Any | None) -> dict[str, Any]:
    if client is None:
        from openai import OpenAI

        client = OpenAI()
    response = client.responses.create(
        model=model,
        input=prompt,
        text={"format": {"type": "json_schema", "name": "capture_processing", "schema": schema, "strict": True}},
    )
    data = _jsonable(response)
    parsed: Any | None = None
    if isinstance(data.get("output_parsed"), dict):
        parsed = data["output_parsed"]
    text = data.get("output_text")
    if parsed is None and isinstance(text, str) and text.strip():
        parsed = json.loads(text)
    if parsed is None:
        for item in data.get("output", []) if isinstance(data.get("output"), list) else []:
            for content in item.get("content", []) if isinstance(item, dict) else []:
                if isinstance(content, dict) and isinstance(content.get("parsed"), dict):
                    parsed = content["parsed"]
                    break
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    parsed = json.loads(content["text"])
                    break
            if parsed is not None:
                break
    if parsed is None:
        raise ValueError("Responses API result did not include structured JSON")
    errors = _validate_schema(parsed, schema)
    if errors:
        raise ValueError("invalid structured output: " + "; ".join(errors))
    return parsed


def _append_or_preview(inbox_root: Path, capture: dict[str, Any], event: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    path = _processing_path(inbox_root, capture)
    if not dry_run:
        append_jsonl(path, event)
    return {"status": "ok", "event_id": capture.get("event_id"), "output": str(path), "event": event, "dry_run": dry_run}


def _build_failed_event(source_event_id: str, stage: str, error: str, *, model: str, now: str | None) -> dict[str, Any]:
    return {
        "event_type": "capture.failed",
        "source_event_id": source_event_id,
        "status": "failed",
        "ts": now or utc_now(),
        "failed_stage": stage,
        "error": {"stage": stage, "message": error, "model": model},
    }


def _derive_event(
    inbox_root: Path,
    event_id: str,
    *,
    stage: str,
    output_key: str,
    schema: dict[str, Any],
    prompt_prefix: str,
    model: str | None,
    client: Any | None,
    now: str | None,
    dry_run: bool,
    force: bool,
    prerequisite: str | None,
    status: str,
) -> dict[str, Any]:
    selected_model = model or os.environ.get("OFFICE_CAPTURE_PROCESSING_MODEL") or DEFAULT_PROCESSING_MODEL
    inbox_root = Path(inbox_root)
    capture = _find_capture(inbox_root, event_id)
    if not capture:
        return {"status": "error", "event_id": event_id, "error": "capture event not found"}
    if not force and _has_stage(capture, stage):
        return {"status": "skipped", "event_id": event_id, "reason": f"already emitted {stage}"}
    if prerequisite and not _has_stage(capture, prerequisite):
        return {"status": "error", "event_id": event_id, "error": f"missing prerequisite {prerequisite}"}
    prompt = prompt_prefix + " Return only schema JSON.\n" + json.dumps(_context(capture), ensure_ascii=False)
    try:
        payload = _structured_response(prompt, schema, model=selected_model, client=client)
    except Exception as exc:
        event = _build_failed_event(event_id, stage, str(exc), model=selected_model, now=now)
        return _append_or_preview(inbox_root, capture, event, dry_run=dry_run) | {"status": "error", "error": str(exc)}
    event = {"event_type": stage, "source_event_id": event_id, "status": status, "ts": now or utc_now(), output_key: payload}
    return _append_or_preview(inbox_root, capture, event, dry_run=dry_run)


def route_event(
    inbox_root: Path,
    event_id: str,
    *,
    model: str | None = None,
    client: Any | None = None,
    now: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    return _derive_event(
        inbox_root,
        event_id,
        stage="capture.routed",
        output_key="routing",
        schema=ROUTING_SCHEMA,
        prompt_prefix="Route this capture into the finite office capture ontology.",
        model=model,
        client=client,
        now=now,
        dry_run=dry_run,
        force=force,
        prerequisite="capture.transcribed",
        status="routed",
    )


def artifactize_event(
    inbox_root: Path,
    event_id: str,
    *,
    model: str | None = None,
    client: Any | None = None,
    now: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    return _derive_event(
        inbox_root,
        event_id,
        stage="capture.artifact_candidate.created",
        output_key="artifact_candidate",
        schema=ARTIFACT_SCHEMA,
        prompt_prefix="Create a concise, reviewable artifact candidate from this routed capture.",
        model=model,
        client=client,
        now=now,
        dry_run=dry_run,
        force=force,
        prerequisite="capture.routed",
        status="artifact_candidate",
    )


def propose_reingest_event(
    inbox_root: Path,
    event_id: str,
    *,
    model: str | None = None,
    client: Any | None = None,
    now: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    return _derive_event(
        inbox_root,
        event_id,
        stage="capture.reingest_candidate.created",
        output_key="reingest_candidate",
        schema=REINGEST_SCHEMA,
        prompt_prefix="Propose a human-approved reingest delta. Do not apply it or mutate office state.",
        model=model,
        client=client,
        now=now,
        dry_run=dry_run,
        force=force,
        prerequisite="capture.artifact_candidate.created",
        status="pending_reingest",
    )


def process_event(
    inbox_root: Path,
    event_id: str,
    *,
    transcription_model: str | None = None,
    model: str | None = None,
    transcription_client: Any | None = None,
    client: Any | None = None,
    now: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    inbox_root = Path(inbox_root)
    steps: list[dict[str, Any]] = []
    capture = _find_capture(inbox_root, event_id)
    if force or not _has_stage(capture, "capture.transcribed"):
        steps.append({"step": "transcribe", **transcribe_event(inbox_root, event_id, model=transcription_model, client=transcription_client, now=now, force=force, dry_run=dry_run)})
        if steps[-1].get("status") not in {"ok", "skipped"}:
            return {"status": "error", "event_id": event_id, "steps": steps}
    capture = _find_capture(inbox_root, event_id)
    if force or not _has_stage(capture, "capture.routed"):
        steps.append({"step": "route", **route_event(inbox_root, event_id, model=model, client=client, now=now, force=force, dry_run=dry_run)})
        if steps[-1].get("status") not in {"ok", "skipped"}:
            return {"status": "error", "event_id": event_id, "steps": steps}
    capture = _find_capture(inbox_root, event_id)
    if force or not _has_stage(capture, "capture.artifact_candidate.created"):
        steps.append({"step": "artifactize", **artifactize_event(inbox_root, event_id, model=model, client=client, now=now, force=force, dry_run=dry_run)})
        if steps[-1].get("status") not in {"ok", "skipped"}:
            return {"status": "error", "event_id": event_id, "steps": steps}
    capture = _find_capture(inbox_root, event_id)
    if force or not _has_stage(capture, "capture.reingest_candidate.created"):
        steps.append({"step": "propose_reingest", **propose_reingest_event(inbox_root, event_id, model=model, client=client, now=now, force=force, dry_run=dry_run)})
        if steps[-1].get("status") not in {"ok", "skipped"}:
            return {"status": "error", "event_id": event_id, "steps": steps}
    return {"status": "ok", "event_id": event_id, "steps": steps, "dry_run": dry_run}

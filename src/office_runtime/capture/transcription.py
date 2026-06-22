from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from office_runtime.capture.lifecycle import PROCESSING_DIR, RAW_FEEDBACK_DIR, _read_jsonl

AUDIO_DIR = "human_feedback_audio"
DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
DEFAULT_MAX_AUDIO_BYTES = 25 * 1024 * 1024
SUPPORTED_AUDIO_EXTENSIONS = {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return json.loads(json.dumps(value, default=lambda o: getattr(o, "__dict__", str(o))))


def _iter_raw_files(inbox_root: Path) -> Iterable[Path]:
    raw_root = inbox_root / RAW_FEEDBACK_DIR
    if not raw_root.exists():
        return []
    return sorted(p for p in raw_root.glob("*.jsonl") if p.is_file())


def _event_id(row: dict[str, Any]) -> str:
    return str(row.get("event_id") or row.get("source_event_id") or "").strip()


def _processing_path(inbox_root: Path, raw_path: Path) -> Path:
    return inbox_root / PROCESSING_DIR / raw_path.name


def _stage_for(row: dict[str, Any]) -> str:
    return str(row.get("event_type") or row.get("stage") or "")


def _existing_stage_ids(inbox_root: Path, stage: str) -> set[str]:
    seen: set[str] = set()
    stream_root = inbox_root / PROCESSING_DIR
    if not stream_root.exists():
        return seen
    for path in sorted(stream_root.glob("*.jsonl")):
        if not path.is_file():
            continue
        for _, row, error in _read_jsonl(path):
            if error or row is None:
                continue
            if _stage_for(row) == stage and row.get("source_event_id"):
                seen.add(str(row["source_event_id"]))
    return seen


def _existing_transcribed_ids(inbox_root: Path) -> set[str]:
    return _existing_stage_ids(inbox_root, "capture.transcribed")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _audio_root(inbox_root: Path, audio_root: Path | None = None) -> Path:
    configured = audio_root or os.environ.get("OFFICE_FEEDBACK_AUDIO_ROOT") or os.environ.get("OFFICE_CAPTURE_AUDIO_ROOT")
    root = Path(configured) if configured else inbox_root / AUDIO_DIR
    return (root if root.is_absolute() else inbox_root.parent / root).resolve()


def _extract_audio_path_value(row: dict[str, Any]) -> str | None:
    for key in ("audio_path", "audio_rel_path"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    audio = row.get("audio")

    if isinstance(audio, dict):
        value = audio.get("rel_path") or audio.get("path")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    if isinstance(audio, str) and audio.strip():
        return audio.strip()

    return None


def _explicit_audio_path_value(row: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    explicit = _extract_audio_path_value(row)
    if explicit:
        return explicit, None, True
    audio = row.get("audio")
    if isinstance(audio, dict):
        return None, "audio.rel_path is missing", True
    if audio is not None:
        return None, "audio must be an object with rel_path or a string path", True
    return None, None, False


def _resolve_explicit_audio_path(path_value: str, audio_root: Path) -> tuple[Path | None, str | None]:
    path = Path(path_value)
    if ".." in path.parts:
        return None, "audio path traversal is not allowed"
    if path.is_absolute():
        return path.resolve(), None

    parts = path.parts
    prefix = ("inbox", AUDIO_DIR)
    if len(parts) >= len(prefix) and parts[: len(prefix)] == prefix:
        path = Path(*parts[len(prefix) :])
    elif parts and parts[0] == AUDIO_DIR:
        path = Path(*parts[1:])
    if not path.parts:
        return None, "audio path is missing"
    return (audio_root / path).resolve(), None


def _candidate_audio_paths(inbox_root: Path, raw_path: Path, row: dict[str, Any], event_id: str, audio_root: Path) -> tuple[list[Path], str | None]:
    explicit, error, had_explicit_audio = _explicit_audio_path_value(row)
    if error:
        return [], error
    if explicit:
        resolved, resolve_error = _resolve_explicit_audio_path(explicit, audio_root)
        if resolve_error or resolved is None:
            return [], resolve_error
        return [resolved], None
    if had_explicit_audio:
        return [], "audio path is missing"
    date_dir = audio_root / raw_path.stem
    return sorted(p.resolve() for p in date_dir.glob(f"{event_id}.*") if p.is_file()), None


def _resolve_audio_path(
    inbox_root: Path,
    raw_path: Path,
    row: dict[str, Any],
    event_id: str,
    *,
    audio_root: Path | None = None,
    max_bytes: int | None = None,
) -> tuple[Path | None, str | None]:
    root = _audio_root(inbox_root, audio_root)
    candidates, candidate_error = _candidate_audio_paths(inbox_root, raw_path, row, event_id, root)
    if candidate_error:
        return None, candidate_error
    if not candidates:
        return None, f"audio not found under {root / raw_path.stem}"
    if len(candidates) > 1:
        return None, f"multiple audio files found for {event_id}: {', '.join(str(p) for p in candidates)}"
    audio_path = candidates[0]
    if not _is_relative_to(audio_path, root):
        return None, f"audio path escapes configured audio root: {audio_path}"
    if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        return None, f"unsupported audio extension: {audio_path.suffix.lower()}"
    if not audio_path.exists() or not audio_path.is_file():
        return None, f"audio not found: {audio_path}"
    limit = max_bytes if max_bytes is not None else int(os.environ.get("OFFICE_CAPTURE_MAX_AUDIO_BYTES", DEFAULT_MAX_AUDIO_BYTES))
    size = audio_path.stat().st_size
    if size <= 0:
        return None, "audio file is empty"
    if size > limit:
        return None, f"audio too large: {size} bytes exceeds {limit}"
    return audio_path, None


def _usage_from(response: dict[str, Any], audio_path: Path) -> dict[str, Any]:
    usage = response.get("usage")
    if isinstance(usage, dict) and usage:
        return usage
    duration = response.get("duration")
    if duration is not None:
        return {"type": "duration", "seconds": duration}
    return {"type": "unknown", "audio_bytes": audio_path.stat().st_size}


def _transcribe_audio(audio_path: Path, *, model: str, client: Any | None = None) -> dict[str, Any]:
    if client is None:
        from openai import OpenAI

        client = OpenAI()
    with audio_path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(model=model, file=audio_file, response_format="json")
    return _jsonable(response)


def build_transcribed_event(source_event_id: str, transcription: dict[str, Any], *, model: str, audio_path: Path, now: str | None = None) -> dict[str, Any]:
    created_at = now or utc_now()
    return {
        "event_type": "capture.transcribed",
        "source_event_id": source_event_id,
        "status": "transcribed",
        "ts": created_at,
        "transcript": {"text": str(transcription.get("text") or ""), "model": model, "created_at": created_at},
        "usage": _usage_from(transcription, audio_path),
    }


def build_transcription_failed_event(source_event_id: str, error: str, *, model: str, now: str | None = None) -> dict[str, Any]:
    return {
        "event_type": "capture.transcription_failed",
        "source_event_id": source_event_id,
        "status": "failed",
        "ts": now or utc_now(),
        "error": {"stage": "transcribe", "message": error, "model": model},
    }


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def transcribe_event(
    inbox_root: Path,
    event_id: str,
    *,
    model: str | None = None,
    client: Any | None = None,
    now: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    audio_root: Path | None = None,
    max_bytes: int | None = None,
) -> dict[str, Any]:
    inbox_root = Path(inbox_root)
    selected_model = model or os.environ.get("OFFICE_CAPTURE_TRANSCRIPTION_MODEL") or DEFAULT_TRANSCRIPTION_MODEL
    if not force and event_id in _existing_transcribed_ids(inbox_root):
        return {"status": "skipped", "event_id": event_id, "reason": "already transcribed"}
    for raw_path in _iter_raw_files(inbox_root):
        for _, row, error in _read_jsonl(raw_path):
            if error or row is None or _event_id(row) != event_id:
                continue
            out = _processing_path(inbox_root, raw_path)
            audio_path, audio_error = _resolve_audio_path(inbox_root, raw_path, row, event_id, audio_root=audio_root, max_bytes=max_bytes)
            if audio_error or audio_path is None:
                return {"status": "error", "event_id": event_id, "error": audio_error}
            try:
                transcription = _transcribe_audio(audio_path, model=selected_model, client=client)
                event = build_transcribed_event(event_id, transcription, model=selected_model, audio_path=audio_path, now=now)
            except Exception as exc:
                event = build_transcription_failed_event(event_id, str(exc), model=selected_model, now=now)
                if not dry_run:
                    append_jsonl(out, event)
                return {"status": "error", "event_id": event_id, "output": str(out), "event": event, "error": str(exc)}
            if not dry_run:
                append_jsonl(out, event)
            return {"status": "ok", "event_id": event_id, "output": str(out), "event": event, "dry_run": dry_run}
    return {"status": "error", "event_id": event_id, "error": "raw capture event not found"}


def transcribe_pending(
    inbox_root: Path,
    *,
    limit: int = 5,
    model: str | None = None,
    client: Any | None = None,
    now: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    inbox_root = Path(inbox_root)
    seen = set() if force else _existing_transcribed_ids(inbox_root)
    results: list[dict[str, Any]] = []
    for raw_path in _iter_raw_files(inbox_root):
        for _, row, error in _read_jsonl(raw_path):
            if len(results) >= limit:
                return {"status": "ok", "processed": len(results), "results": results}
            if error or row is None:
                continue
            event_id = _event_id(row)
            if not event_id or event_id in seen:
                continue
            result = transcribe_event(inbox_root, event_id, model=model, client=client, now=now, force=force, dry_run=dry_run)
            results.append(result)
            if result.get("status") == "ok":
                seen.add(event_id)
    return {"status": "ok", "processed": len(results), "results": results}

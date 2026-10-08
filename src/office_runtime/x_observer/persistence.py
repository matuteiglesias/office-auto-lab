"""Portable filesystem evidence store with atomic writes and cursor CAS."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .contracts import ObserverContractError


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@dataclass(frozen=True)
class StoredPage:
    run_id: str
    page_number: int
    page_sha256: str
    path: str


class EvidenceStore:
    """Local adapter; object-store adapters can implement the same operations."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write_page(self, *, run_id: str, page_number: int, payload: Mapping[str, Any]) -> StoredPage:
        if not run_id or page_number < 1:
            raise ObserverContractError("run_id and positive page_number are required")
        digest = hashlib.sha256(_json(payload).encode()).hexdigest()
        path = self.root / "pages" / run_id / f"{page_number:06d}-{digest}.json"
        _atomic(path, _json({"schema_version": "x.observer.page.evidence.v0.1", "run_id": run_id, "page_number": page_number, "page_sha256": digest, "payload": payload}) + "\n")
        return StoredPage(run_id, page_number, digest, str(path))

    def write_manifest(self, run_id: str, manifest: Mapping[str, Any]) -> Path:
        path = self.root / "runs" / f"{run_id}.json"
        _atomic(path, _json({"schema_version": "x.observer.run.manifest.v0.1", **manifest}) + "\n")
        return path

    def commit_page(self, *, user_id: str, run_id: str, page_number: int,
                    payload: Mapping[str, Any], expected_revision: int | None,
                    project: Callable[[Mapping[str, Any]], None],
                    cursor: Mapping[str, Any]) -> StoredPage:
        """Persist evidence, project it, then advance the cursor last."""
        stored = self.write_page(run_id=run_id, page_number=page_number, payload=payload)
        project(payload)
        self.write_manifest(run_id, {"run_id": run_id, "page_number": page_number, "page_sha256": stored.page_sha256, "projection": "committed"})
        self.compare_and_set_cursor(user_id, expected_revision, cursor)
        return stored

    def read_cursor(self, user_id: str) -> dict[str, Any] | None:
        path = self.root / "cursors" / f"{user_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def compare_and_set_cursor(self, user_id: str, expected_revision: int | None, cursor: Mapping[str, Any]) -> None:
        current = self.read_cursor(user_id)
        actual = None if current is None else current.get("revision")
        if actual != expected_revision:
            raise ObserverContractError("cursor revision conflict")
        revision = 0 if expected_revision is None else expected_revision + 1
        value = {"schema_version": "x.observer.cursor.v0.1", **cursor, "revision": revision}
        _atomic(self.root / "cursors" / f"{user_id}.json", _json(value) + "\n")

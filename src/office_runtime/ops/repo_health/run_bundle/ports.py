from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Protocol

from .model import canonical_json, sha256_hex, validate_run_bundle


class DuplicateRunError(RuntimeError):
    pass


class PolicySource(Protocol):
    def read_snapshot(self) -> Mapping[str, Any]: ...


class RunEvidenceSink(Protocol):
    def write(self, bundle: Mapping[str, Any]) -> Mapping[str, Any]: ...


class HistorySink(Protocol):
    def append(self, bundle: Mapping[str, Any]) -> Mapping[str, Any]: ...


class LatestSignalSink(Protocol):
    def publish(self, signal: Mapping[str, Any]) -> None: ...


class FilePolicySource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read_snapshot(self) -> Mapping[str, Any]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("policy snapshot must be an object")
        return data


class LocalRunEvidenceSink:
    """Atomically create an immutable run directory; exact replay is a no-op."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, bundle: Mapping[str, Any]) -> Mapping[str, Any]:
        validate_run_bundle(bundle)
        payload = canonical_json(bundle)
        run_id = str(bundle["run"]["run_id"])
        final_dir = self.root / run_id
        bundle_path = final_dir / "run_bundle.json"
        if final_dir.exists():
            if bundle_path.is_file() and bundle_path.read_bytes() == payload:
                return {"status": "duplicate", "run_id": run_id, "path": str(final_dir), "sha256": sha256_hex(payload)}
            raise DuplicateRunError(f"run_id {run_id!r} already exists with different content")
        self.root.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix=f".{run_id}.", dir=self.root))
        try:
            (temp_dir / "run_bundle.json").write_bytes(payload)
            manifest = {"schema_version": "repo_health.run_manifest.v1", "run_id": run_id,
                        "files": {"run_bundle.json": {"sha256": sha256_hex(payload), "bytes": len(payload)}}}
            (temp_dir / "manifest.json").write_bytes(canonical_json(manifest))
            os.rename(temp_dir, final_dir)
        except FileExistsError:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return self.write(bundle)
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        return {"status": "created", "run_id": run_id, "path": str(final_dir), "sha256": sha256_hex(payload)}


class JsonlHistorySink:
    """Local append history with deterministic duplicate-run suppression."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, bundle: Mapping[str, Any]) -> Mapping[str, Any]:
        validate_run_bundle(bundle)
        run_id = str(bundle["run"]["run_id"])
        existing = []
        if self.path.exists():
            existing = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]
        matches = [row for row in existing if row.get("run", {}).get("run_id") == run_id]
        if matches:
            if canonical_json(matches[0]) == canonical_json(bundle):
                return {"status": "duplicate", "run_id": run_id}
            raise DuplicateRunError(f"history already contains conflicting run_id {run_id!r}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(canonical_json(bundle))
            handle.flush()
            os.fsync(handle.fileno())
        return {"status": "appended", "run_id": run_id}


class AtomicLatestSignalSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def publish(self, signal: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(canonical_json(signal))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise

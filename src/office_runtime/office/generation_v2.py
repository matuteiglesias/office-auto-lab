from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd

from .config import OfficeConfig
from .control_snapshot import build_snapshot, read_control_tower_v2
from .execution import compile_execution_plan
from .invariants import validate_forward_generation
from .principal import compile_principal_brief, render_principal_markdown
from .run_records import build_run_record, write_run_record
from .work_items import compile_work_items
from office_runtime.staff.preparation_v2 import LocalRepoEvidenceAdapter, SnapshotEvidenceAdapter, prepare_work_items


SCHEMA_VERSION = "ops.office-generation.v2"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class GenerationV2Error(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _validate_run_id(run_id: str) -> str:
    value = str(run_id or "").strip()
    if not RUN_ID_RE.fullmatch(value):
        raise GenerationV2Error("run_id must be a short filesystem-safe identifier")
    return value


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_digest(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "item"


def _v2_root(out_root: Path) -> Path:
    return out_root / "v2"


def _load_current_brief(v2_root: Path) -> dict | None:
    pointer = v2_root / "current.json"
    if not pointer.exists():
        return None
    try:
        current = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenerationV2Error("current v2 generation pointer is unreadable") from exc
    run_id = _validate_run_id(str(current.get("run_id", "")))
    brief_path = v2_root / "runs" / run_id / "principal" / "brief.json"
    if not brief_path.is_file():
        raise GenerationV2Error("current v2 generation pointer references a missing Principal brief")
    try:
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenerationV2Error("current v2 Principal brief is unreadable") from exc
    if str(brief.get("schema_version", "")) != "ops.principal-brief.v2":
        raise GenerationV2Error("current v2 Principal brief has an unsupported schema")
    return brief


def _artifact_hashes(run_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.relative_to(run_dir).as_posix()] = _sha256_file(path)
    return hashes


def _publish_current(v2_root: Path, run_id: str, manifest: dict) -> None:
    pointer = {
        "schema_version": "ops.office-current-pointer.v2",
        "run_id": run_id,
        "run_path": f"runs/{run_id}",
        "manifest_digest": manifest["manifest_digest"],
        "source_snapshot_digest": manifest["lineage"]["snapshot_digest"],
        "published_at": manifest["published_at"],
    }
    tmp = v2_root / f".current.{run_id}.tmp"
    _write_json(tmp, pointer)
    os.replace(tmp, v2_root / "current.json")


def compile_generation_from_frames(
    frames: Mapping[str, pd.DataFrame],
    *,
    out_root: Path,
    run_id: str,
    spreadsheet_id: str = "",
    observed_at: str | None = None,
    prepared_at: str | None = None,
    published_at: str | None = None,
    max_deep: int = 6,
    include_local_repo_evidence: bool = False,
    previous_brief: dict | None = None,
    publish: bool = True,
    trigger: str = "manual",
) -> dict:
    """Compile and publish one coherent Office v2 generation.

    All downstream artifacts derive from one in-memory snapshot. Nothing reads
    Control Tower again during this function. Run evidence is part of the
    publication protocol: a published current pointer always has a canonical
    run record for the same generation.
    """
    run_id = _validate_run_id(run_id)
    out_root = Path(out_root)
    v2_root = _v2_root(out_root)
    final_dir = v2_root / "runs" / run_id
    staging_dir = v2_root / ".staging" / run_id
    record_path = v2_root / "run_records" / f"{run_id}.json"
    if final_dir.exists() or staging_dir.exists() or record_path.exists():
        raise GenerationV2Error(f"run_id {run_id!r} already exists")

    if previous_brief is None:
        previous_brief = _load_current_brief(v2_root)

    stage_names = ("snapshot", "work", "staff", "principal", "execution", "invariants", "manifest", "promotion", "run_record", "publication")
    stage_results = {name: {"status": "PENDING"} for name in stage_names}
    current_stage = "snapshot"
    started_at = _now_iso()
    snapshot_digest = ""
    manifest_digest = ""
    counts: dict[str, int] = {}
    manifest: dict = {}

    staging_dir.parent.mkdir(parents=True, exist_ok=True)
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        current_stage = "snapshot"
        snapshot = build_snapshot(
            frames,
            observed_at=observed_at,
            spreadsheet_id=spreadsheet_id,
        )
        snapshot_digest = str(snapshot.get("snapshot_digest", ""))
        _write_json(staging_dir / "control" / "snapshot.json", snapshot)
        stage_results[current_stage] = {"status": "OK"}

        current_stage = "work"
        work_set = compile_work_items(snapshot)
        _write_json(staging_dir / "routing" / "work_items.json", work_set)
        stage_results[current_stage] = {"status": "OK"}

        current_stage = "staff"
        adapters = [SnapshotEvidenceAdapter()]
        if include_local_repo_evidence:
            adapters.append(LocalRepoEvidenceAdapter())
        preparation = prepare_work_items(
            snapshot,
            work_set,
            adapters=adapters,
            max_deep=max_deep,
            prepared_at=prepared_at or _now_iso(),
        )
        _write_json(staging_dir / "staff" / "preparation.json", preparation)
        packet_dir = staging_dir / "staff" / "packets"
        packet_dir.mkdir(parents=True, exist_ok=True)
        for packet in preparation.get("packets", []) or []:
            packet_id = str(packet.get("staff_packet_id", ""))
            _write_json(packet_dir / f"{_safe_name(packet_id)}.json", packet)
        stage_results[current_stage] = {"status": "OK"}

        current_stage = "principal"
        principal = compile_principal_brief(preparation, previous_brief=previous_brief)
        _write_json(staging_dir / "principal" / "brief.json", principal)
        principal_md = staging_dir / "principal" / "brief.md"
        principal_md.parent.mkdir(parents=True, exist_ok=True)
        principal_md.write_text(render_principal_markdown(principal), encoding="utf-8")
        stage_results[current_stage] = {"status": "OK"}

        current_stage = "execution"
        execution = compile_execution_plan(snapshot, principal)
        _write_json(staging_dir / "execution" / "plan.json", execution)
        execution_packet_dir = staging_dir / "execution" / "packets"
        execution_packet_dir.mkdir(parents=True, exist_ok=True)
        for packet in execution.get("packets", []) or []:
            packet_id = str(packet.get("execution_packet_id", ""))
            _write_json(execution_packet_dir / f"{_safe_name(packet_id)}.json", packet)
        stage_results[current_stage] = {"status": "OK"}

        current_stage = "invariants"
        invariant_checks = validate_forward_generation(snapshot, work_set, preparation, principal, execution)
        stage_results[current_stage] = {"status": "OK", "checks": invariant_checks}

        lineage = {
            "snapshot_digest": snapshot["snapshot_digest"],
            "work_set_schema": work_set["schema_version"],
            "source_work_snapshot_digest": work_set["source_snapshot_digest"],
            "preparation_digest": preparation["preparation_digest"],
            "source_preparation_snapshot_digest": preparation["source_snapshot_digest"],
            "principal_brief_digest": principal["brief_digest"],
            "source_principal_snapshot_digest": principal["source_snapshot_digest"],
            "execution_plan_digest": execution["plan_digest"],
            "source_execution_snapshot_digest": execution["source_snapshot_digest"],
        }
        if len({
            lineage["snapshot_digest"],
            lineage["source_work_snapshot_digest"],
            lineage["source_preparation_snapshot_digest"],
            lineage["source_principal_snapshot_digest"],
            lineage["source_execution_snapshot_digest"],
        }) != 1:
            raise GenerationV2Error("generation lineage diverged across v2 stages")

        current_stage = "manifest"
        published = published_at or _now_iso()
        counts = {
            "work_items": work_set.get("counts", {}).get("work_items", 0),
            "staff_packets": len(preparation.get("packets", []) or []),
            "principal_needs_you": principal.get("counts", {}).get("needs_you", 0),
            "principal_ready_pulls": principal.get("counts", {}).get("ready_pulls", 0),
            "principal_exceptions": principal.get("counts", {}).get("exceptions", 0),
            "execution_packets": execution.get("counts", {}).get("packets", 0),
            "execution_exceptions": execution.get("counts", {}).get("exceptions", 0),
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "run_id": run_id,
            "published_at": published,
            "lineage": lineage,
            "counts": counts,
            "settings": {
                "max_deep": max_deep,
                "local_repo_evidence": include_local_repo_evidence,
            },
            "invariants": invariant_checks,
            "artifact_hashes": _artifact_hashes(staging_dir),
        }
        manifest["manifest_digest"] = _stable_digest(manifest)
        manifest_digest = str(manifest["manifest_digest"])
        _write_json(staging_dir / "manifest.json", manifest)
        stage_results[current_stage] = {"status": "OK"}

        current_stage = "promotion"
        os.replace(staging_dir, final_dir)
        stage_results[current_stage] = {"status": "OK"}

        current_stage = "run_record"
        stage_results[current_stage] = {"status": "OK"}
        pre_publication_status = "SHADOW" if not publish else "NOT_PUBLISHED"
        pre_record = build_run_record(
            run_id=run_id,
            trigger=trigger,
            started_at=started_at,
            finished_at=_now_iso(),
            status="SUCCEEDED",
            publication_status=pre_publication_status,
            stage_results=stage_results,
            source_snapshot_digest=snapshot_digest,
            manifest_digest=manifest_digest,
            counts=counts,
            run_path=f"v2/runs/{run_id}",
        )
        write_run_record(out_root, pre_record)

        if publish:
            current_stage = "publication"
            v2_root.mkdir(parents=True, exist_ok=True)
            _publish_current(v2_root, run_id, manifest)
            stage_results[current_stage] = {"status": "OK"}
            final_record = build_run_record(
                run_id=run_id,
                trigger=trigger,
                started_at=started_at,
                finished_at=_now_iso(),
                status="SUCCEEDED",
                publication_status="PUBLISHED",
                stage_results=stage_results,
                source_snapshot_digest=snapshot_digest,
                manifest_digest=manifest_digest,
                counts=counts,
                run_path=f"v2/runs/{run_id}",
            )
            write_run_record(out_root, final_record)
        else:
            stage_results["publication"] = {"status": "SKIPPED", "reason": "SHADOW"}
            shadow_record = build_run_record(
                run_id=run_id,
                trigger=trigger,
                started_at=started_at,
                finished_at=_now_iso(),
                status="SUCCEEDED",
                publication_status="SHADOW",
                stage_results=stage_results,
                source_snapshot_digest=snapshot_digest,
                manifest_digest=manifest_digest,
                counts=counts,
                run_path=f"v2/runs/{run_id}",
            )
            write_run_record(out_root, shadow_record)

        return {
            "status": "ok",
            "run_id": run_id,
            "run_dir": str(final_dir),
            "run_record": str(record_path),
            "manifest": manifest,
            "published": publish,
        }
    except Exception as exc:
        if current_stage in stage_results:
            stage_results[current_stage] = {"status": "FAILED", "error_type": type(exc).__name__}
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        try:
            failure_record = build_run_record(
                run_id=run_id,
                trigger=trigger,
                started_at=started_at,
                finished_at=_now_iso(),
                status="FAILED",
                publication_status="NOT_PUBLISHED",
                stage_results=stage_results,
                source_snapshot_digest=snapshot_digest,
                manifest_digest=manifest_digest,
                counts=counts,
                failures=[{"stage": current_stage, "type": type(exc).__name__, "message": str(exc)}],
                run_path=f"v2/runs/{run_id}" if final_dir.exists() else "",
            )
            write_run_record(out_root, failure_record)
        except Exception:
            pass
        raise


def run_generation_v2(
    cfg: OfficeConfig,
    *,
    run_id: str | None = None,
    max_deep: int = 6,
    include_local_repo_evidence: bool = False,
    publish: bool = True,
    trigger: str = "manual",
) -> dict:
    frames = read_control_tower_v2(cfg)
    return compile_generation_from_frames(
        frames,
        out_root=cfg.out_root,
        run_id=run_id or new_run_id(),
        spreadsheet_id=cfg.spreadsheet_id,
        max_deep=max_deep,
        include_local_repo_evidence=include_local_repo_evidence,
        publish=publish,
        trigger=trigger,
    )

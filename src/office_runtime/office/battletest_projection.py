"""Lineage-safe deterministic battle-test review projections."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ops.battletest-projection.v1"
MARKER = "<!-- office_projection_lineage: "


class BattleTestProjectionError(ValueError):
    pass


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BattleTestProjectionError(f"unreadable projection input: {path}") from exc
    if not isinstance(value, dict):
        raise BattleTestProjectionError(f"projection input must be an object: {path}")
    return value


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _write_markdown(path: Path, lineage: dict, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = MARKER + json.dumps(lineage, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + " -->"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text("\n".join([marker, "", *lines, ""]), encoding="utf-8")
    os.replace(temporary, path)


def _lineage(run_dir: Path, manifest: dict, *, generated_at: str) -> dict:
    source = manifest.get("lineage", {}) or {}
    required = {
        "source_generation_run_id": str(manifest.get("run_id", "")),
        "source_snapshot_digest": str(source.get("snapshot_digest", "")),
        "source_preparation_digest": str(source.get("preparation_digest", "")),
        "source_principal_brief_digest": str(source.get("principal_brief_digest", "")),
        "generated_at": str(generated_at),
    }
    if not all(required.values()):
        raise BattleTestProjectionError(f"generation manifest is missing required lineage: {run_dir}")
    return required


def _load_generation(run_dir: Path, *, generated_at: str) -> tuple[dict, dict, dict, dict, dict]:
    manifest = _read_json(run_dir / "manifest.json")
    snapshot = _read_json(run_dir / "control" / "snapshot.json")
    preparation = _read_json(run_dir / "staff" / "preparation.json")
    principal = _read_json(run_dir / "principal" / "brief.json")
    execution = _read_json(run_dir / "execution" / "plan.json")
    lineage = _lineage(run_dir, manifest, generated_at=generated_at)
    if str(snapshot.get("snapshot_digest", "")) != lineage["source_snapshot_digest"]:
        raise BattleTestProjectionError("snapshot does not match generation manifest")
    if str(preparation.get("source_snapshot_digest", "")) != lineage["source_snapshot_digest"]:
        raise BattleTestProjectionError("preparation does not match generation snapshot")
    if str(preparation.get("preparation_digest", "")) != lineage["source_preparation_digest"]:
        raise BattleTestProjectionError("preparation digest does not match generation manifest")
    if str(principal.get("source_snapshot_digest", "")) != lineage["source_snapshot_digest"]:
        raise BattleTestProjectionError("Principal brief does not match generation snapshot")
    if str(principal.get("source_preparation_digest", "")) != lineage["source_preparation_digest"]:
        raise BattleTestProjectionError("Principal brief does not match preparation")
    if str(principal.get("brief_digest", "")) != lineage["source_principal_brief_digest"]:
        raise BattleTestProjectionError("Principal brief digest does not match generation manifest")
    if str(execution.get("source_snapshot_digest", "")) != lineage["source_snapshot_digest"]:
        raise BattleTestProjectionError("execution plan does not match generation snapshot")
    if str(execution.get("source_principal_brief_digest", "")) != lineage["source_principal_brief_digest"]:
        raise BattleTestProjectionError("execution plan does not match Principal brief")
    return lineage, snapshot, preparation, principal, execution


def _stamped(lineage: dict, **payload: Any) -> dict:
    return {"schema_version": SCHEMA_VERSION, "projection_lineage": dict(lineage), **payload}


def _bullet_lines(rows: list[dict], formatter: Any) -> list[str]:
    return [formatter(row) for row in rows] if rows else ["- None."]


def render_battletest_projection(run_dir: Path, out_root: Path, *, generated_at: str) -> dict:
    """Render the close/preparation review surface from exactly one v2 run."""
    run_dir = Path(run_dir)
    out_root = Path(out_root)
    lineage, snapshot, preparation, principal, execution = _load_generation(run_dir, generated_at=generated_at)
    close = out_root / "2026-09-14-close"
    prep = out_root / "2026-09-15-prep"
    artifacts = [
        "2026-09-14-close/manifest.json", "2026-09-14-close/day_close.md", "2026-09-14-close/movement.json",
        "2026-09-14-close/open_work.json", "2026-09-14-close/exceptions.json", "2026-09-14-close/evidence_index.json", "2026-09-14-close/qa_notes.md",
        "2026-09-15-prep/manifest.json", "2026-09-15-prep/morning_brief.md", "2026-09-15-prep/principal.json",
        "2026-09-15-prep/staff_index.json", "2026-09-15-prep/ready_pulls.json", "2026-09-15-prep/waiting.json",
        "2026-09-15-prep/exceptions.json", "2026-09-15-prep/execution_plan.json", "2026-09-15-prep/source_evidence.json", "2026-09-15-prep/qa_notes.md",
    ]
    counts = dict((manifest := _read_json(run_dir / "manifest.json")).get("counts", {}) or {})
    _write_json(close / "manifest.json", _stamped(lineage, artifact_role="sep14_close", counts=counts, artifacts=[name for name in artifacts if name.startswith("2026-09-14-close/")]))
    _write_json(prep / "manifest.json", _stamped(lineage, artifact_role="sep15_preparation", counts=counts, artifacts=[name for name in artifacts if name.startswith("2026-09-15-prep/")]))
    _write_json(close / "movement.json", _stamped(lineage, generation_status=manifest.get("status", ""), generation_counts=counts))
    _write_json(close / "open_work.json", _stamped(lineage, staff_counts=preparation.get("counts", {}), principal_follow_up=principal.get("staff_follow_up", [])))
    _write_json(close / "exceptions.json", _stamped(lineage, exceptions=principal.get("exceptions", [])))
    _write_json(close / "evidence_index.json", _stamped(lineage, run_path=str(run_dir), snapshot_digest=snapshot.get("snapshot_digest", ""), preparation_digest=preparation.get("preparation_digest", ""), principal_brief_digest=principal.get("brief_digest", ""), execution_plan_digest=execution.get("plan_digest", "")))
    _write_markdown(close / "day_close.md", lineage, [
        "# September 14 close", "", "Deterministic projection from one coherent Office v2 generation; this is not an AI-assisted narrative.",
        "", f"- Work items: {counts.get('work_items', 0)}", f"- Deep Staff preparation: {preparation.get('deep_by_lane', {})}",
        f"- Budget deferred: {preparation.get('counts', {}).get('DEFERRED_BY_BUDGET', 0)}", f"- True front-level exceptions: {principal.get('counts', {}).get('exceptions', 0)}",
    ])
    _write_markdown(close / "qa_notes.md", lineage, ["# Close QA notes", "", "Projection lineage validated against snapshot, preparation, Principal, and execution artifacts."])
    _write_json(prep / "principal.json", _stamped(lineage, principal_brief=principal))
    _write_json(prep / "staff_index.json", _stamped(lineage, staff_counts=preparation.get("counts", {}), deep_by_lane=preparation.get("deep_by_lane", {}), lane_budgets=preparation.get("lane_budgets", {})))
    _write_json(prep / "ready_pulls.json", _stamped(lineage, ready_pulls=principal.get("ready_pulls", [])))
    _write_json(prep / "waiting.json", _stamped(lineage, staff_follow_up=principal.get("staff_follow_up", [])))
    _write_json(prep / "exceptions.json", _stamped(lineage, exceptions=principal.get("exceptions", [])))
    _write_json(prep / "execution_plan.json", _stamped(lineage, execution_plan=execution))
    _write_json(prep / "source_evidence.json", _stamped(lineage, run_path=str(run_dir), source_snapshot_digest=snapshot.get("snapshot_digest", ""), source_preparation_digest=preparation.get("preparation_digest", ""), source_principal_brief_digest=principal.get("brief_digest", "")))
    morning_lines = [
        "# Tuesday Sep 15", "", "Deterministic preparation projection. No Sep 15 execution evidence exists.",
        "", "## Needs you", "",
        *_bullet_lines(principal.get("needs_you", []), lambda row: f"- {row.get('title', '')}"),
        "", "## Ready pulls", "",
        *_bullet_lines(principal.get("ready_pulls", []), lambda row: f"- {row.get('title', '')}"),
        "", "## True exceptions", "",
        *_bullet_lines(principal.get("exceptions", []), lambda row: f"- {row.get('title', '')}: {row.get('exception_code', '')}"),
    ]
    _write_markdown(prep / "morning_brief.md", lineage, morning_lines)
    _write_markdown(prep / "qa_notes.md", lineage, ["# Tuesday preparation QA", "", "Projection lineage validated. Ready pulls remain presentation objects; this projection does not execute them."])
    current = _stamped(lineage, artifacts=artifacts)
    _write_json(out_root / "projection_current.json", current)
    validate_projection_bundle(out_root)
    return current


def _artifact_lineage(path: Path) -> dict:
    if path.suffix == ".json":
        return _read_json(path).get("projection_lineage", {}) or {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(MARKER) and line.endswith(" -->"):
            try:
                return json.loads(line[len(MARKER):-4])
            except json.JSONDecodeError as exc:
                raise BattleTestProjectionError(f"invalid Markdown lineage marker: {path}") from exc
    raise BattleTestProjectionError(f"missing Markdown lineage marker: {path}")


def validate_projection_bundle(out_root: Path) -> dict:
    """Fail closed if review artifacts do not bind to one exact generation."""
    root = Path(out_root)
    current = _read_json(root / "projection_current.json")
    expected = current.get("projection_lineage", {}) or {}
    required = {"source_generation_run_id", "source_snapshot_digest", "source_preparation_digest", "source_principal_brief_digest", "generated_at"}
    if set(expected) != required or not all(str(expected[key]).strip() for key in required):
        raise BattleTestProjectionError("projection current manifest has incomplete lineage")
    artifacts = current.get("artifacts", []) or []
    if not artifacts:
        raise BattleTestProjectionError("projection current manifest has no artifacts")
    for relative in artifacts:
        path = root / str(relative)
        if not path.is_file():
            raise BattleTestProjectionError(f"projection artifact is missing: {relative}")
        if _artifact_lineage(path) != expected:
            raise BattleTestProjectionError(f"projection artifact lineage diverged: {relative}")
    return {"status": "ok", "source_generation_run_id": expected["source_generation_run_id"], "artifacts": len(artifacts)}

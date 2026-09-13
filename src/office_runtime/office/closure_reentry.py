"""Read-only Office consumer for ``artifact:ops.closure@1``.

Ops owns the closure facts.  This module only validates, reconciles and renders
them as Office review material.  In particular it never writes Carry State,
horizon, priority, escalation state, or follow-up work.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CONTRACT = "artifact:ops.closure@1"
LOCAL_CONTRACT = "artifact:ops.office-reentry-proposal@1"
STATUSES = {"done", "partial", "blocked", "no-change"}
CARRY = {"Active", "Watch", "Support-needed", "Escalate", "Parked"}
HORIZONS = {"Today", "This week", "This month", "Later", "maintenance", "Health rev"}


class ClosureValidationError(ValueError):
    """A supplied Ops closure is invalid and therefore cannot be silently used."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_source_ref(path: Path, root: Path | None = None) -> str:
    """A durable source reference deliberately excludes machine-local paths."""
    if root is not None:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    return path.name


def _as_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ClosureValidationError(f"{field} must be a list")
    return value


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClosureValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _load_json_file(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClosureValidationError(f"cannot read closure input {path.name}: {exc}") from exc
    try:
        if path.suffix.lower() == ".jsonl":
            values = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            value = json.loads(text)
            values = value.get("closures", []) if isinstance(value, dict) and "closures" in value else [value]
    except json.JSONDecodeError as exc:
        raise ClosureValidationError(f"invalid JSON in closure input {path.name}: {exc.msg}") from exc
    if not all(isinstance(value, dict) for value in values):
        raise ClosureValidationError(f"closure input {path.name} must contain objects")
    return values


def load_closures(source: Path) -> list[tuple[dict[str, Any], str]]:
    """Read one JSON/JSONL file or a non-recursive directory of those files.

    Explicit operator input is the scope boundary. YAML is intentionally not
    guessed: Ops currently has documentation authority but no checked-in YAML
    schema or parser dependency.
    """
    source = source.expanduser().resolve()
    if not source.exists():
        raise ClosureValidationError("closure input does not exist")
    if source.is_file():
        files = [source]
        root = source.parent
    elif source.is_dir():
        files = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in {".json", ".jsonl"})
        root = source
        if not files:
            raise ClosureValidationError("closure directory contains no JSON or JSONL files")
    else:
        raise ClosureValidationError("closure input must be a regular file or directory")
    rows: list[tuple[dict[str, Any], str]] = []
    for path in files:
        rows.extend((value, _safe_source_ref(path, root)) for value in _load_json_file(path))
    return rows


def validate_closure(raw: dict[str, Any], source_ref: str) -> dict[str, Any]:
    """Validate and normalize documented upstream semantics without changing them."""
    contract = raw.get("contract") or raw.get("schema")
    if contract is not None and contract != CONTRACT:
        raise ClosureValidationError(f"unexpected closure contract: {contract}")
    front_id = _nonempty_string(raw.get("front_id"), "front_id")
    status = raw.get("status")
    if status not in STATUSES:
        raise ClosureValidationError("status must be done, partial, blocked, or no-change")
    evidence = _as_list(raw.get("evidence"), "evidence")
    if not evidence:
        raise ClosureValidationError("evidence must not be empty")
    closure = raw.get("closure")
    if not isinstance(closure, (str, dict)) or (isinstance(closure, str) and not closure.strip()):
        raise ClosureValidationError("closure must be a non-empty string or object")
    next_touch = raw.get("next_touch")
    if status in {"partial", "blocked"}:
        _nonempty_string(next_touch, "next_touch")
    elif next_touch is not None and not isinstance(next_touch, str):
        raise ClosureValidationError("next_touch must be a string or null")
    carry = raw.get("carry_recommendation")
    if carry not in CARRY:
        raise ClosureValidationError("carry_recommendation is not an allowed Ops recommendation")
    horizon = raw.get("horizon_recommendation")
    if horizon is not None and horizon not in HORIZONS:
        raise ClosureValidationError("horizon_recommendation is not an allowed recommendation")
    escalation = raw.get("escalation")
    if escalation is None:
        escalation_state: Any = "not supplied"
    elif isinstance(escalation, (bool, str, dict)):
        escalation_state = escalation
    else:
        raise ClosureValidationError("escalation must be a boolean, string, object, or absent")
    follow_up = raw.get("follow_up_spawns")
    if follow_up is not None:
        _as_list(follow_up, "follow_up_spawns")
    repo_evidence = raw.get("repo_evidence")
    if repo_evidence is not None:
        _as_list(repo_evidence, "repo_evidence")
    stable_upstream = raw.get("closure_id") or raw.get("id") or raw.get("run_id")
    if stable_upstream is not None:
        stable_upstream = _nonempty_string(stable_upstream, "closure_id")
    content = dict(raw)
    content.pop("source_ref", None)
    source_sha256 = _sha256(content)
    closure_ref = stable_upstream or f"closure:sha256:{source_sha256}"
    return {
        "contract": CONTRACT,
        "closure_ref": closure_ref,
        "front_id": front_id,
        "status": status,
        "evidence": evidence,
        "closure": closure,
        "next_touch": next_touch,
        "carry_recommendation": carry,
        "horizon_recommendation": horizon if horizon is not None else "not supplied",
        "follow_up_spawns": follow_up if follow_up is not None else "not supplied",
        "escalation": escalation_state,
        "repo_evidence": repo_evidence if repo_evidence is not None else "not supplied",
        "notes": raw.get("notes", "not supplied"),
        "source_ref": source_ref,
        "source_sha256": source_sha256,
    }


def reconcile_closures(rows: Iterable[tuple[dict[str, Any], str]], front_df: Any) -> list[dict[str, Any]]:
    # Kept lazy so Office compile can import this optional consumer without a
    # circular import; Front Registry authority remains in compile.py.
    from .compile import FRONT_ID_PRIMARY, canonicalize_front_identity

    fronts = canonicalize_front_identity(front_df)
    known = {str(value).strip() for value in fronts.get(FRONT_ID_PRIMARY, []) if str(value).strip()}
    output: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for raw, source_ref in rows:
        normalized = validate_closure(raw, source_ref)
        prior = seen.get(normalized["closure_ref"])
        if prior is not None:
            if prior != normalized["source_sha256"]:
                raise ClosureValidationError("same closure identity carries different content")
            continue
        seen[normalized["closure_ref"]] = normalized["source_sha256"]
        normalized["front_reconciliation_status"] = "RECONCILED" if normalized["front_id"] in known else "UNRESOLVED_FRONT"
        output.append(normalized)
    return sorted(output, key=lambda row: (row["front_id"], row["closure_ref"]))


def _closure_text(closure: Any) -> str:
    if isinstance(closure, str):
        return closure.strip()
    return _canonical_json(closure)


def make_proposals(closures: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for closure in closures:
        reconciled = closure["front_reconciliation_status"] == "RECONCILED"
        actionable = reconciled and closure["status"] in {"partial", "blocked", "no-change"}
        seed = None
        if reconciled and closure["status"] in {"partial", "blocked"}:
            seed = {
                "front_id": closure["front_id"],
                "previous_closure": closure["closure_ref"],
                "status": closure["status"],
                "what_became_true": _closure_text(closure["closure"]),
                "evidence": closure["evidence"],
                "exact_next_touch": closure["next_touch"],
                "carry_recommendation": closure["carry_recommendation"],
                "horizon_recommendation": closure["horizon_recommendation"],
                "escalation": closure["escalation"],
            }
        proposals.append({
            "contract": LOCAL_CONTRACT,
            "proposal_ref": f"office-reentry:{closure['closure_ref']}",
            "closure_ref": closure["closure_ref"],
            "front_id": closure["front_id"],
            "front_reconciliation_status": closure["front_reconciliation_status"],
            "status": closure["status"],
            "what_became_true": _closure_text(closure["closure"]),
            "what_remains": closure["next_touch"] if closure["status"] != "done" else "No restart work proposed by this done closure.",
            "evidence": closure["evidence"],
            "exact_restart_instruction": closure["next_touch"],
            "carry_recommendation": closure["carry_recommendation"],
            "horizon_recommendation": closure["horizon_recommendation"],
            "escalation": closure["escalation"],
            "follow_up_spawns": closure["follow_up_spawns"],
            "actionable": actionable,
            "mutation_performed": False,
            "restart_seed": seed,
        })
    return proposals


def render_reentry_review(proposals: Iterable[dict[str, Any]]) -> str:
    proposals = list(proposals)
    out = ["## Recent closures / reentry", "", "Read-only Ops closure evidence and Office proposals. Recommendations are not Carry, horizon, priority, or escalation mutations.", ""]
    if not proposals:
        return "\n".join(out + ["- status: unconfigured or no closures supplied", ""])
    for proposal in proposals:
        out += [f"### Front {proposal['front_id']} — {proposal['status']} ({proposal['front_reconciliation_status']})", "", f"- Closure: {proposal['what_became_true']}", f"- Evidence: {', '.join(map(str, proposal['evidence']))}"]
        if proposal["front_reconciliation_status"] != "RECONCILED":
            out += ["- Review warning: unknown front; no actionable Office proposal was created.", ""]
            continue
        out += [
            f"- Exact next touch: {proposal['exact_restart_instruction'] or 'none (no restart supplied by this closure)'}",
            f"- Proposed carry posture: {proposal['carry_recommendation']} (proposal only)",
            f"- Proposed horizon: {proposal['horizon_recommendation']} (proposal only)",
            f"- Escalation supplied by Ops: {proposal['escalation']}",
            "",
        ]
    return "\n".join(out)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def compile_reentry(source: Path, front_df: Any, out_dir: Path) -> dict[str, Any]:
    """Compile a bounded source into deterministic substantive Office artifacts."""
    rows = load_closures(source)
    closures = reconcile_closures(rows, front_df)
    proposals = make_proposals(closures)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "normalized_closures.jsonl", closures)
    _write_jsonl(out_dir / "reentry_proposals.jsonl", proposals)
    (out_dir / "reentry_review.md").write_text(render_reentry_review(proposals), encoding="utf-8")
    qa = {
        "status": "ok",
        "mutation_performed": False,
        "closures_read": len(rows),
        "closures_normalized": len(closures),
        "reconciled": sum(row["front_reconciliation_status"] == "RECONCILED" for row in closures),
        "unresolved": sum(row["front_reconciliation_status"] != "RECONCILED" for row in closures),
        "proposals": len(proposals),
        "restart_seeds": sum(row["restart_seed"] is not None for row in proposals),
        "done_closures": sum(row["status"] == "done" for row in closures),
        "no_change_closures": sum(row["status"] == "no-change" for row in closures),
        "validation_failures": 0,
    }
    output_hashes = {name: hashlib.sha256((out_dir / name).read_bytes()).hexdigest() for name in ("normalized_closures.jsonl", "reentry_proposals.jsonl", "reentry_review.md")}
    manifest = {
        "contract": "artifact:ops.office-reentry-run@1",
        "input_contract": CONTRACT,
        "source_refs": sorted({row["source_ref"] for row in closures}),
        "source_hashes": {row["closure_ref"]: row["source_sha256"] for row in closures},
        "front_reconciliation": {row["closure_ref"]: row["front_reconciliation_status"] for row in closures},
        "output_hashes": output_hashes,
        "mutation_performed": False,
        "qa": qa,
    }
    (out_dir / "qa.json").write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "ok", "out": str(out_dir), "manifest": str(out_dir / "manifest.json"), **qa}

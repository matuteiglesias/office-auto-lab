from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .ir import IssueIR, ProjectIR, issue_to_trigger, project_to_target
from .classify import classify_row
from .spec.load_v0 import load_archetypes, load_operator_registry



@dataclass
class CandidateBlock:
    archetype: str
    mode: str
    duration_min: int
    title: str
    triggers: List[IssueIR]
    targets: List[ProjectIR]
    score_total: float
    score_components: Dict[str, float]


def _load_operator_meta() -> Dict[str, Dict[str, Any]]:
    reg = load_operator_registry()
    out: Dict[str, Dict[str, Any]] = {}
    for op in reg.get("operators", []):
        out[op["op_id"]] = op
    return out


def parse_frontier_rows(rows: Iterable[Dict[str, Any]]) -> List[IssueIR]:
    issues: List[IssueIR] = []
    for r in rows:
        project_id = str(r.get("project_id", "")).strip()
        plugin = str(r.get("plugin", "")).strip()
        bucket = str(r.get("bucket", "")).strip()
        normalized_class = str(r.get("normalized_class", "")).strip()
        short_diag = str(r.get("short_diag", "")).strip()
        run_id = str(r.get("run_id", "")).strip()
        ts_started = r.get("ts_started")
        try:
            ts_started = int(ts_started) if ts_started not in (None, "", "nan") else None
        except Exception:
            ts_started = None

        c = classify_row(r)
        issues.append(
            IssueIR(
                project_id=project_id,
                plugin=plugin,
                bucket=bucket,
                normalized_class=normalized_class,
                severity=c["severity"],
                issue_type=c["issue_type"],
                signature=c["signature"],
                short_diag=short_diag,
                run_id=run_id,
                ts_started=ts_started,
                raw=dict(r),
            )
        )
    return issues


def rollup_projects(issues: List[IssueIR]) -> Dict[str, ProjectIR]:
    projs: Dict[str, ProjectIR] = {}
    for i in issues:
        if not i.project_id:
            continue
        p = projs.setdefault(i.project_id, ProjectIR(project_id=i.project_id))
        p.issues.append(i)

    for p in projs.values():
        p.derive()

    return projs


def score_block(mode: str, triggers: List[IssueIR], targets: List[ProjectIR]) -> Tuple[float, Dict[str, float]]:
    # Deterministic, explainable v0 scoring
    w = {
        "system_error": 10.0,
        "actionable_failure": 6.0,
        "ineligible": 3.0,
        "warning": 1.0,
        "ok": 0.0,
    }
    sev = sum(w.get(t.severity, 0.0) for t in triggers)
    distinct_projects = len({t.project_id for t in triggers})
    context_penalty = max(0, distinct_projects - 1) * 1.5

    components = {
        "severity_sum": sev,
        "distinct_projects": float(distinct_projects),
        "context_penalty": -context_penalty,
    }
    total = sev - context_penalty
    return total, components


def _select_projects_by_issue(projects: Dict[str, ProjectIR], issue_types: List[str]) -> List[ProjectIR]:
    out: List[ProjectIR] = []
    wanted = set(issue_types)
    for p in projects.values():
        its = {i.issue_type for i in p.issues}
        if its & wanted:
            out.append(p)
    return out


def _trigger_issues_for_projects(project_ids: List[str], issues: List[IssueIR], issue_types: List[str]) -> List[IssueIR]:
    wanted = set(issue_types)
    out: List[IssueIR] = []
    for i in issues:
        if i.project_id in project_ids and i.issue_type in wanted:
            out.append(i)
    return out


def generate_candidate_blocks(date: str, projects: Dict[str, ProjectIR], issues: List[IssueIR]) -> List[CandidateBlock]:
    spec = load_archetypes()
    archetypes = spec.get("archetypes", [])
    candidates: List[CandidateBlock] = []

    for a in archetypes:
        archetype_id = a["archetype"]
        mode = a["mode"]
        duration_min = int(a.get("duration_min", 90))
        max_projects = int(a.get("max_projects", 3))

        # selection logic: v0 uses fixed mapping by archetype id
        if archetype_id == "substrate_bootstrap_sweep":
            pool = _select_projects_by_issue(projects, ["repo_path_missing", "makefile_missing", "repo_not_git"])
            # prioritize projects with blockers and higher severity
            pool = sorted(pool, key=lambda p: (-(len(p.blockers)), p.project_id))
            selected = pool[:max_projects]

        elif archetype_id == "plugin_boundary_fix":
            pool = _select_projects_by_issue(projects, ["plugin_not_loaded"])
            pool = sorted(pool, key=lambda p: (p.project_id))
            selected = pool[:1]

        elif archetype_id == "smoke_failure_triage":
            pool = _select_projects_by_issue(projects, ["cmd_nonzero"])
            pool = [p for p in pool if p.can_run_smoke and not p.blockers]
            pool = sorted(pool, key=lambda p: p.project_id)
            selected = pool[:max_projects]

        elif archetype_id == "shared_root_cause_elimination":
            # v0: do not emit this unless you later add triage artifact ingestion
            continue

        elif archetype_id == "runbook_sweep":
            pool = _select_projects_by_issue(projects, ["runbook_missing"])
            pool = sorted(pool, key=lambda p: p.project_id)
            selected = pool[:max_projects]

        elif archetype_id == "hygiene_cleanup":
            pool = _select_projects_by_issue(projects, ["worktree_dirty"])
            pool = sorted(pool, key=lambda p: p.project_id)
            selected = pool[:max_projects]

        elif archetype_id == "season_decisions":
            pool = _select_projects_by_issue(projects, ["staleness_old_commit"])
            pool = sorted(pool, key=lambda p: p.project_id)
            selected = pool[:max_projects]

        else:
            continue

        if not selected:
            continue

        selected_ids = [p.project_id for p in selected]

        # triggers: issues that caused inclusion
        if archetype_id == "substrate_bootstrap_sweep":
            trig = _trigger_issues_for_projects(selected_ids, issues, ["repo_path_missing", "makefile_missing", "repo_not_git"])
        elif archetype_id == "plugin_boundary_fix":
            trig = _trigger_issues_for_projects(selected_ids, issues, ["plugin_not_loaded"])
        elif archetype_id == "smoke_failure_triage":
            trig = _trigger_issues_for_projects(selected_ids, issues, ["cmd_nonzero"])
        elif archetype_id == "runbook_sweep":
            trig = _trigger_issues_for_projects(selected_ids, issues, ["runbook_missing"])
        elif archetype_id == "hygiene_cleanup":
            trig = _trigger_issues_for_projects(selected_ids, issues, ["worktree_dirty"])
        elif archetype_id == "season_decisions":
            trig = _trigger_issues_for_projects(selected_ids, issues, ["staleness_old_commit"])
        else:
            trig = []

        title = f"{mode}: {archetype_id.replace('_', ' ')}"

        total, comps = score_block(mode, trig, selected)
        candidates.append(
            CandidateBlock(
                archetype=archetype_id,
                mode=mode,
                duration_min=duration_min,
                title=title,
                triggers=trig,
                targets=selected,
                score_total=total,
                score_components=comps,
            )
        )

    # rank high to low
    candidates.sort(key=lambda c: (-(c.score_total), c.archetype))
    return candidates


def candidate_to_prepared_block(date: str, c: CandidateBlock) -> Dict[str, Any]:
    op_meta = _load_operator_meta()
    arche_spec = {a["archetype"]: a for a in load_archetypes().get("archetypes", [])}[c.archetype]
    plan_template = arche_spec.get("operator_plan_template", [])

    operator_plan: List[Dict[str, Any]] = []
    for step in plan_template:
        op_id = step["op_id"]
        meta = op_meta.get(op_id, {})
        evidence_pattern = meta.get("evidence_pattern", "unknown_evidence")
        operator_plan.append(
            {
                "op_id": op_id,
                "timebox_min": int(step.get("timebox_min", meta.get("default_timebox_min", 15))),
                "stop_rule": f"Stop at timebox for {op_id}",
                "expected_evidence": [f"evidence:{evidence_pattern}"],
            }
        )

    triggers = [issue_to_trigger(i) for i in c.triggers]
    targets = [project_to_target(p, sorted({i.signature for i in p.issues})) for p in c.targets]

    # expected deltas: coarse v0 statements
    deltas: List[Dict[str, Any]] = []
    for p in c.targets:
        for it in sorted(p.blockers | p.warnings):
            deltas.append({"project_id": p.project_id, "from_issue_type": it, "to_state": "reclassified"})

    block_id = f"{date}:{c.archetype}:{','.join([p.project_id for p in c.targets])}"

    pb: Dict[str, Any] = {
        "block_id": block_id,
        "date": date,
        "duration_min": c.duration_min,
        "mode": c.mode,
        "archetype": c.archetype,
        "title": c.title,
        "triggers": triggers,
        "targets": targets,
        "operator_plan": operator_plan,
        "expected_frontier_deltas": deltas if deltas else [{"project_id": c.targets[0].project_id, "from_issue_type": "unknown", "to_state": "reclassified"}],
        "stop_rules": [
            "One block one mode",
            "No sheet wiring in v0 compiler blocks",
            "Stop if feasibility is violated and write a LockIn note",
        ],
        "acceptance": [
            "prepared_blocks.jsonl exists",
            "3-6 blocks emitted (for fixture-sized input)",
            "no PIPELINE block includes targets with blockers",
        ],
        "score": {"total": c.score_total, "components": c.score_components},
        "notes": "",
    }
    return pb


def write_jsonl(path: Path, blocks: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for b in blocks:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

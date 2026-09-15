from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from office_runtime.office.identity import IdentityResolutionError, IdentityResolver


SCHEMA_VERSION = "ops.staff-preparation-set.v2"
PACKET_SCHEMA_VERSION = "ops.staff-packet.v2"
DEEP_KINDS = frozenset({"DECIDE", "UNBLOCK", "VERIFY", "EXECUTE"})
PREPARATION_LANE_BUDGETS = {"DECISION": 2, "ACTION": 3, "REPAIR_VERIFY": 1}
DECISION_MATURITY = frozenset({"NOT_A_DECISION", "NEEDS_MORE_PREP", "WAITING_FOR_EVIDENCE", "READY_FOR_PRINCIPAL"})
KIND_RANK = {"DECIDE": 0, "UNBLOCK": 1, "VERIFY": 2, "EXECUTE": 3, "MAINTAIN": 4}
HORIZON_RANK = {"TODAY": 0, "THIS_WEEK": 1, "THIS_MONTH": 2, "MAINTENANCE": 3, "LATER": 4}
QUESTION_BY_KIND = {
    "DECIDE": "What bounded principal decision is actually required now?",
    "UNBLOCK": "What is the smallest missing fact or repair that would make this item actionable?",
    "VERIFY": "What evidence would establish whether the current state is healthy enough to proceed?",
    "EXECUTE": "What is the smallest credible execution step and what evidence would prove it completed?",
    "MAINTAIN": "What bounded maintenance touch preserves continuity without widening scope?",
}


class StaffPreparationError(ValueError):
    pass


class EvidenceAdapter(Protocol):
    name: str

    def collect(self, snapshot: dict, work_item: dict) -> dict:
        ...


def _rows(snapshot: dict, table: str) -> list[dict]:
    rows = snapshot.get("tables", {}).get(table, {}).get("rows", [])
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _by_front(snapshot: dict, table: str) -> dict[str, dict]:
    return {str(row.get("front_id", "")).strip(): row for row in _rows(snapshot, table) if str(row.get("front_id", "")).strip()}


def _stable_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _priority_tuple(item: dict) -> tuple[int, int, int, str]:
    return (
        0 if item.get("principal_required") else 1,
        KIND_RANK.get(str(item.get("kind", "")).upper(), 99),
        HORIZON_RANK.get(str(item.get("horizon", "")).upper(), 50),
        str(item.get("work_item_id", "")),
    )


def preparation_lane(work_item: dict) -> str:
    """Return the deterministic Staff preparation lane for typed work."""
    kind = str(work_item.get("kind", "")).upper()
    if kind == "DECIDE":
        return "DECISION"
    if kind in {"EXECUTE", "MAINTAIN"}:
        return "ACTION"
    if kind == "VERIFY" and work_item.get("human_focus"):
        return "ACTION"
    return "REPAIR_VERIFY"


@dataclass(frozen=True)
class TriageResult:
    work_item_id: str
    front_id: str
    kind: str
    status: str
    prep_depth: str
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "work_item_id": self.work_item_id,
            "front_id": self.front_id,
            "kind": self.kind,
            "status": self.status,
            "prep_depth": self.prep_depth,
            "reasons": list(self.reasons),
        }


def triage_work_item(work_item: dict) -> TriageResult:
    work_item_id = str(work_item.get("work_item_id", "")).strip()
    front_id = str(work_item.get("front_id", "")).strip()
    kind = str(work_item.get("kind", "")).strip().upper()
    if not work_item_id or not front_id or kind not in KIND_RANK:
        raise StaffPreparationError("work item is missing stable identity or supported kind")

    identity = work_item.get("identity", {}) or {}
    identity_status = str(identity.get("status", "")).upper()
    workspace_statuses = {str(row.get("status", "")).upper() for row in identity.get("workspace_states", []) or []}
    if identity_status == "ERROR":
        return TriageResult(work_item_id, front_id, kind, "BLOCKED", "LIGHT", ("IDENTITY_ERROR",))
    decision_dependency = work_item.get("decision_dependency", {}) or {}
    dependency_status = str(decision_dependency.get("status", "")).upper() if isinstance(decision_dependency, dict) else ""
    if kind in {"UNBLOCK", "VERIFY", "EXECUTE", "MAINTAIN"} and dependency_status in {"PENDING", "BLOCKED", "UNRESOLVED"}:
        return TriageResult(work_item_id, front_id, kind, "BLOCKED", "LIGHT", ("DECISION_DEPENDENCY_UNRESOLVED",))
    if kind == "UNBLOCK" and (
        identity_status == "NOT_READY" or workspace_statuses.intersection({"AMBIGUOUS", "UNRESOLVED", "UNAVAILABLE"})
    ):
        return TriageResult(work_item_id, front_id, kind, "BLOCKED", "LIGHT", ("IDENTITY_NOT_READY",))

    prep_mode = str(work_item.get("prep_mode", "")).upper()
    if kind == "MAINTAIN" and prep_mode == "NONE":
        return TriageResult(work_item_id, front_id, kind, "NO_DEEP_PREP_REQUIRED", "LIGHT", ("BOUNDED_MAINTENANCE",))
    if kind in DEEP_KINDS or prep_mode == "STAFF_REQUIRED":
        reasons = ["NEAR_PULL_FRONTIER"]
        if work_item.get("principal_required"):
            reasons.append("PRINCIPAL_REQUIRED")
        return TriageResult(work_item_id, front_id, kind, "READY_FOR_PREP", "DEEP", tuple(reasons))
    return TriageResult(work_item_id, front_id, kind, "READY_LIGHT", "LIGHT", ("LIGHT_PREPARATION_ONLY",))


class SnapshotEvidenceAdapter:
    name = "control_snapshot"

    def collect(self, snapshot: dict, work_item: dict) -> dict:
        front_id = str(work_item.get("front_id", "")).strip()
        runtime = _by_front(snapshot, "runtime_health_v2").get(front_id, {})
        support = [row for row in _rows(snapshot, "support_artifacts_v2") if str(row.get("front_id", "")).strip() == front_id and str(row.get("status", "")).strip().upper() not in {"RETIRED", "DEPRECATED"}]
        contracts = [row for row in _rows(snapshot, "operator_contract_v2") if str(row.get("front_id", "")).strip() == front_id and str(row.get("contract_status", "")).strip().upper() == "ACTIVE"]
        return {
            "adapter": self.name,
            "status": "ok",
            "runtime": {key: runtime.get(key, "") for key in ("health_status", "health_bucket", "last_observed_at", "last_observed_by", "short_diag", "evidence_ref", "source_run_id", "generated_at") if key in runtime},
            "support_artifacts": [
                {key: row.get(key, "") for key in ("artifact_id", "artifact_role", "artifact_kind", "authority_class", "status", "uri", "source_ref", "note") if key in row and str(row.get(key, "")).strip()}
                for row in support
            ],
            "operator_contracts": [
                {key: row.get(key, "") for key in ("contract_id", "operator_name", "operator_class", "contract_version", "allowed_powers", "forbidden_powers", "required_seams", "must_consume_shared_modules", "must_not_implement_locally") if key in row and str(row.get(key, "")).strip()}
                for row in contracts
            ],
        }


class LocalRepoEvidenceAdapter:
    """Collect bounded Git evidence through governed workspace identity.

    Concrete paths are used only inside this adapter and never returned in the
    portable Staff packet.
    """

    name = "local_repo"

    @staticmethod
    def _git(path: Path, *args: str) -> tuple[bool, str]:
        try:
            proc = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, type(exc).__name__
        return proc.returncode == 0, (proc.stdout or proc.stderr or "").strip()

    def collect(self, snapshot: dict, work_item: dict) -> dict:
        front_id = str(work_item.get("front_id", "")).strip()
        try:
            context = IdentityResolver(snapshot).execution_context(front_id)
        except IdentityResolutionError as exc:
            return {"adapter": self.name, "status": "blocked", "reason": str(exc)}
        primary = context.get("primary_repository")
        repos = [primary] if primary else context.get("repositories", [])
        repos = [repo for repo in repos if repo]
        if not repos:
            return {"adapter": self.name, "status": "not_applicable", "reason": "front has no repository binding"}
        repo = repos[0]
        workspace = repo.get("workspace", {}) or {}
        if workspace.get("status") != "RESOLVED" or not workspace.get("local_path"):
            return {"adapter": self.name, "status": "blocked", "repo_id": repo.get("repo_id"), "workspace_id": workspace.get("workspace_id"), "reason": workspace.get("reason") or "workspace is not resolved"}
        path = Path(str(workspace["local_path"]))
        if not path.is_dir():
            return {"adapter": self.name, "status": "blocked", "repo_id": repo.get("repo_id"), "workspace_id": workspace.get("workspace_id"), "reason": "resolved workspace path is not present on this machine"}
        ok_head, head = self._git(path, "rev-parse", "HEAD")
        ok_branch, branch = self._git(path, "branch", "--show-current")
        ok_status, porcelain = self._git(path, "status", "--porcelain")
        return {
            "adapter": self.name,
            "status": "ok" if ok_head else "degraded",
            "repo_id": repo.get("repo_id"),
            "workspace_id": workspace.get("workspace_id"),
            "revision": head if ok_head else "",
            "branch": branch if ok_branch else "",
            "dirty": bool(porcelain) if ok_status else None,
            "git_status_observed": ok_status,
        }


def _current_state(snapshot: dict, work_item: dict) -> dict:
    runtime = _by_front(snapshot, "runtime_health_v2").get(str(work_item.get("front_id", "")).strip(), {})
    return {
        "carry_status": work_item.get("carry_status", ""),
        "horizon": work_item.get("horizon", ""),
        "priority_mode": work_item.get("priority_mode", ""),
        "principal_mode": work_item.get("principal_mode", ""),
        "needs": (work_item.get("context", {}) or {}).get("needs", ""),
        "note": (work_item.get("context", {}) or {}).get("note", ""),
        "runtime": {
            "health_status": runtime.get("health_status", ""),
            "health_bucket": runtime.get("health_bucket", ""),
            "short_diag": runtime.get("short_diag", ""),
            "source_run_id": runtime.get("source_run_id", ""),
        },
    }


def _blockers(work_item: dict, evidence: list[dict]) -> list[str]:
    out: list[str] = []
    identity = work_item.get("identity", {}) or {}
    if str(identity.get("status", "")).upper() in {"ERROR", "NOT_READY"}:
        out.append("identity is not ready")
    for row in identity.get("workspace_states", []) or []:
        status = str(row.get("status", "")).upper()
        if status in {"AMBIGUOUS", "UNRESOLVED", "UNAVAILABLE"}:
            out.append(f"workspace {row.get('workspace_id') or '<unresolved>'} is {status.lower()}")
    decision_dependency = work_item.get("decision_dependency", {}) or {}
    if isinstance(decision_dependency, dict) and str(decision_dependency.get("status", "")).upper() in {"PENDING", "BLOCKED", "UNRESOLVED"}:
        out.append(f"decision dependency {decision_dependency.get('decision_id') or '<unnamed>'} is unresolved")
    for result in evidence:
        if result.get("status") == "blocked":
            out.append(f"{result.get('adapter')}: {result.get('reason', 'blocked')}")
    return list(dict.fromkeys(out))


def _recommended_move(work_item: dict, blockers: list[str]) -> str:
    if blockers:
        return "Resolve the first explicit blocker before widening preparation or execution."
    return {
        "DECIDE": "Present the bounded choice, evidence, and default to the principal; delegate only after that choice is made.",
        "UNBLOCK": "Resolve one missing fact or seam that turns the item into a typed executable or verifiable next step.",
        "VERIFY": "Run the smallest evidence-producing check that can confirm or falsify the current health assumption.",
        "EXECUTE": "Pull one bounded execution step with explicit acceptance evidence and stop after that unit completes.",
        "MAINTAIN": "Perform only the minimum continuity-preserving touch; do not create a new build lane.",
    }.get(str(work_item.get("kind", "")).upper(), "Clarify the next bounded move.")


def _packet(snapshot: dict, work_item: dict, triage: TriageResult, evidence: list[dict], *, prepared_at: str, preparation_status: str) -> dict:
    blockers = _blockers(work_item, evidence)
    uncertainties: list[str] = []
    if not evidence:
        uncertainties.append("no evidence adapter was run")
    runtime_status = _current_state(snapshot, work_item)["runtime"].get("health_status", "")
    if not runtime_status or runtime_status.upper() == "UNKNOWN":
        uncertainties.append("runtime health is unknown")
    if str(work_item.get("kind", "")).upper() == "DECIDE":
        decision_maturity = str(work_item.get("decision_maturity", "NEEDS_MORE_PREP")).upper()
        if decision_maturity not in DECISION_MATURITY - {"NOT_A_DECISION"}:
            decision_maturity = "NEEDS_MORE_PREP"
        decision = work_item.get("decision", {}) if isinstance(work_item.get("decision"), dict) else {}
    else:
        decision_maturity = "NOT_A_DECISION"
        decision = {}
    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "staff_packet_id": "sp:" + str(work_item.get("work_item_id", "")),
        "work_item_id": work_item.get("work_item_id"),
        "front_id": work_item.get("front_id"),
        "title": work_item.get("title", ""),
        "kind": work_item.get("kind"),
        "preparation_status": preparation_status,
        "preparation_lane": preparation_lane(work_item),
        "triage": triage.as_dict(),
        "question": QUESTION_BY_KIND.get(str(work_item.get("kind", "")).upper(), ""),
        "current_state": _current_state(snapshot, work_item),
        "identity": work_item.get("identity", {}),
        "evidence": evidence,
        "uncertainties": uncertainties,
        "blockers": blockers,
        "recommended_move": _recommended_move(work_item, blockers),
        "principal_posture": str(work_item.get("principal_mode", "")).upper(),
        "principal_needed": str(work_item.get("kind", "")).upper() == "DECIDE",
        "principal_question": "Choose or authorize the bounded next move for this item." if str(work_item.get("kind", "")).upper() == "DECIDE" else "",
        "decision_dependency": work_item.get("decision_dependency", {}) if isinstance(work_item.get("decision_dependency"), dict) else {},
        "prepared_at": prepared_at,
        "source_snapshot_digest": snapshot.get("snapshot_digest", ""),
        "decision_maturity": decision_maturity,
        "decision": decision,
    }
    packet["packet_digest"] = _stable_digest(packet)
    return packet


def prepare_work_items(snapshot: dict, work_set: dict, *, adapters: list[EvidenceAdapter] | None = None, max_deep: int = 6, prepared_at: str = "") -> dict:
    """Prepare typed work without rereading governance state."""
    snapshot_digest = str(snapshot.get("snapshot_digest", "")).strip()
    source_digest = str(work_set.get("source_snapshot_digest", "")).strip()
    if not snapshot_digest or snapshot_digest != source_digest:
        raise StaffPreparationError("work set does not belong to the supplied Control Tower snapshot")
    if max_deep < 0:
        raise StaffPreparationError("max_deep must be non-negative")

    adapters = list(adapters) if adapters is not None else [SnapshotEvidenceAdapter()]
    items = [dict(item) for item in work_set.get("work_items", [])]
    items.sort(key=_priority_tuple)
    triage_rows = [triage_work_item(item) for item in items]
    triage_by_id = {row.work_item_id: row for row in triage_rows}

    eligible = [
        item for item in items
        if triage_by_id[str(item.get("work_item_id", ""))].prep_depth == "DEEP"
        and triage_by_id[str(item.get("work_item_id", ""))].status == "READY_FOR_PREP"
    ]
    by_lane: dict[str, list[dict]] = {lane: [] for lane in PREPARATION_LANE_BUDGETS}
    for item in eligible:
        by_lane[preparation_lane(item)].append(item)
    selected_ids: set[str] = set()
    for lane, budget in PREPARATION_LANE_BUDGETS.items():
        for item in by_lane[lane][:budget]:
            if len(selected_ids) >= max_deep:
                break
            selected_ids.add(str(item.get("work_item_id", "")))
    if len(selected_ids) < max_deep:
        spill_order = ("ACTION", "REPAIR_VERIFY", "DECISION")
        selected_by_lane = {
            lane: sum(1 for item in by_lane[lane] if str(item.get("work_item_id", "")) in selected_ids)
            for lane in PREPARATION_LANE_BUDGETS
        }
        under_budget = [
            item for lane in spill_order
            for item in by_lane[lane]
            if str(item.get("work_item_id", "")) not in selected_ids
            and selected_by_lane[lane] < PREPARATION_LANE_BUDGETS[lane]
        ]
        spill_candidates = under_budget + [
            item for lane in spill_order
            for item in by_lane[lane]
            if str(item.get("work_item_id", "")) not in selected_ids and item not in under_budget
        ]
        for item in spill_candidates:
            selected_ids.add(str(item.get("work_item_id", "")))
            if len(selected_ids) >= max_deep:
                break

    deep_used = len(selected_ids)
    packets: list[dict] = []
    for item in items:
        triage = triage_by_id[str(item.get("work_item_id", ""))]
        item_id = str(item.get("work_item_id", ""))
        run_deep = item_id in selected_ids
        if triage.prep_depth == "DEEP" and triage.status == "READY_FOR_PREP" and not run_deep:
            packets.append(_packet(snapshot, item, triage, [], prepared_at=prepared_at, preparation_status="DEFERRED_BY_BUDGET"))
            continue

        evidence: list[dict] = []
        if triage.status != "BLOCKED":
            for adapter in adapters:
                evidence.append(adapter.collect(snapshot, item))
        else:
            evidence.append(SnapshotEvidenceAdapter().collect(snapshot, item))

        if run_deep:
            prep_status = "PREPARED_DEEP"
        elif triage.status == "BLOCKED":
            prep_status = "BLOCKED"
        else:
            prep_status = "PREPARED_LIGHT"
        packets.append(_packet(snapshot, item, triage, evidence, prepared_at=prepared_at, preparation_status=prep_status))

    counts: dict[str, int] = {}
    for packet in packets:
        key = str(packet.get("preparation_status", ""))
        counts[key] = counts.get(key, 0) + 1
    result = {
        "schema_version": SCHEMA_VERSION,
        "source_snapshot_digest": snapshot_digest,
        "source_work_set_schema": work_set.get("schema_version", ""),
        "max_deep": max_deep,
        "deep_used": deep_used,
        "lane_budgets": dict(PREPARATION_LANE_BUDGETS),
        "deep_by_lane": {
            lane: sum(1 for packet in packets if packet.get("preparation_status") == "PREPARED_DEEP" and packet.get("preparation_lane") == lane)
            for lane in PREPARATION_LANE_BUDGETS
        },
        "triage": [row.as_dict() for row in triage_rows],
        "packets": packets,
        "counts": counts,
    }
    result["preparation_digest"] = _stable_digest(result)
    return result

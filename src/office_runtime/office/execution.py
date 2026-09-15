from __future__ import annotations

import hashlib
import json
from typing import Any

from .action_contracts import ActionContractError, validate_action_contract


PLAN_SCHEMA_VERSION = "ops.execution-plan.v2"
PACKET_SCHEMA_VERSION = "ops.execution-packet.v2"
WITHHELD_POWERS = frozenset({"update_state", "open_work_items"})
SUPPORTED_KINDS = frozenset({"UNBLOCK", "VERIFY", "EXECUTE", "MAINTAIN"})


class ExecutionCompileError(ValueError):
    pass


def _stable_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _rows(snapshot: dict, table: str) -> list[dict]:
    rows = snapshot.get("tables", {}).get(table, {}).get("rows", [])
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def _active_contracts(snapshot: dict, front_id: str) -> list[dict]:
    return [
        row
        for row in _rows(snapshot, "operator_contract_v2")
        if str(row.get("front_id", "")).strip() == front_id
        and str(row.get("contract_status", "")).strip().upper() == "ACTIVE"
    ]


def _select_contract(snapshot: dict, front_id: str) -> dict | None:
    contracts = _active_contracts(snapshot, front_id)
    if not contracts:
        return None
    primary = [row for row in contracts if str(row.get("operator_name", "")).strip() == "primary_operator"]
    if len(primary) > 1:
        raise ExecutionCompileError(f"front_id {front_id!r} has multiple ACTIVE primary_operator contracts")
    if len(primary) == 1:
        return primary[0]
    if len(contracts) == 1:
        return contracts[0]
    raise ExecutionCompileError(f"front_id {front_id!r} has multiple ACTIVE operator contracts and no unique primary_operator")


def _target(entry: dict) -> tuple[dict, str | None]:
    context = entry.get("entry_context", {}) or {}
    repo_ids = [str(value).strip() for value in context.get("repo_ids", []) or [] if str(value).strip()]
    workspace_states = [dict(row) for row in context.get("workspace_states", []) or []]
    unresolved = [row for row in workspace_states if str(row.get("status", "")).upper() != "RESOLVED"]
    target = {
        "front_id": entry.get("front_id", ""),
        "repo_ids": repo_ids,
        "workspaces": workspace_states,
    }
    if repo_ids and unresolved:
        return target, "repository target is not fully resolved"
    return target, None


def _operator_envelope(contract: dict) -> dict:
    allowed = _split_semicolon(contract.get("allowed_powers"))
    forbidden = _split_semicolon(contract.get("forbidden_powers"))
    effective = [power for power in allowed if power not in WITHHELD_POWERS]
    withheld = [power for power in allowed if power in WITHHELD_POWERS]
    return {
        "contract_id": str(contract.get("contract_id", "")),
        "operator_name": str(contract.get("operator_name", "")),
        "operator_class": str(contract.get("operator_class", "")),
        "contract_version": str(contract.get("contract_version", "")),
        "effective_allowed_powers": effective,
        "contract_forbidden_powers": forbidden,
        "compiler_withheld_powers": withheld,
        "required_seams": _split_semicolon(contract.get("required_seams")),
        "must_consume_shared_modules": _split_semicolon(contract.get("must_consume_shared_modules")),
        "must_not_implement_locally": _split_semicolon(contract.get("must_not_implement_locally")),
    }


def _packet(snapshot: dict, brief: dict, entry: dict, contract: dict) -> dict:
    kind = str(entry.get("kind", "")).strip().upper()
    action_contract = validate_action_contract(entry.get("action_contract"), front_id=str(entry.get("front_id", "")))
    target, target_error = _target(entry)
    if target_error:
        raise ExecutionCompileError(target_error)
    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "execution_packet_id": "xp:" + str(entry.get("work_item_id", "")),
        "work_item_id": str(entry.get("work_item_id", "")),
        "front_id": str(entry.get("front_id", "")),
        "kind": kind,
        "objective": str(action_contract["objective"]).strip(),
        "why_now": str(action_contract["why_now"]).strip(),
        "target": {"entry_surface": action_contract["entry_surface"], "repository_context": target},
        "operator": _operator_envelope(contract),
        "evidence_inputs": list(entry.get("evidence_refs", []) or []),
        "scope_boundary": str(action_contract["scope_boundary"]).strip(),
        "acceptance_conditions": list(action_contract["acceptance_conditions"]),
        "stop_conditions": list(action_contract["stop_conditions"]),
        "expected_evidence": list(action_contract["expected_evidence"]),
        "known_uncertainties": list(action_contract.get("known_uncertainties", [])),
        "decision_dependencies": list(action_contract.get("decision_dependencies", [])),
        "authorization": {
            "mode": "READY_PULL",
            "source_principal_brief_digest": str(brief.get("brief_digest", "")),
            "source_entry_digest": str(entry.get("entry_digest", "")),
            "principal_decision_inferred": False,
        },
        "source_snapshot_digest": str(snapshot.get("snapshot_digest", "")),
    }
    packet["packet_digest"] = _stable_digest(packet)
    return packet


def compile_execution_plan(snapshot: dict, principal_brief: dict) -> dict:
    """Compile non-principal ready pulls into bounded execution envelopes.

    `needs_you` entries are never interpreted as approval. A decision must first
    be reconciled into governed state and surface as executable work on a
    subsequent Office run.
    """
    snapshot_digest = str(snapshot.get("snapshot_digest", "")).strip()
    brief_digest = str(principal_brief.get("source_snapshot_digest", "")).strip()
    if not snapshot_digest or snapshot_digest != brief_digest:
        raise ExecutionCompileError("Principal brief does not belong to the supplied Control Tower snapshot")
    if str(principal_brief.get("schema_version", "")) != "ops.principal-brief.v2":
        raise ExecutionCompileError("unsupported Principal brief schema")

    packets: list[dict] = []
    exceptions: list[dict] = []
    for entry in principal_brief.get("ready_pulls", []) or []:
        front_id = str(entry.get("front_id", "")).strip()
        work_item_id = str(entry.get("work_item_id", "")).strip()
        kind = str(entry.get("kind", "")).strip().upper()
        if kind not in SUPPORTED_KINDS:
            exceptions.append({
                "work_item_id": work_item_id,
                "front_id": front_id,
                "code": "UNSUPPORTED_EXECUTION_KIND",
                "detail": kind,
            })
            continue
        contract = _select_contract(snapshot, front_id)
        if contract is None:
            exceptions.append({
                "work_item_id": work_item_id,
                "front_id": front_id,
                "code": "NO_ACTIVE_OPERATOR_CONTRACT",
                "detail": "ready pull cannot be compiled safely without an active operator contract",
            })
            continue
        try:
            packets.append(_packet(snapshot, principal_brief, entry, contract))
        except ActionContractError as exc:
            exceptions.append({
                "work_item_id": work_item_id,
                "front_id": front_id,
                "code": "ACTION_CONTRACT_NOT_READY",
                "detail": str(exc),
            })
        except ExecutionCompileError as exc:
            exceptions.append({
                "work_item_id": work_item_id,
                "front_id": front_id,
                "code": "TARGET_NOT_READY",
                "detail": str(exc),
            })

    ignored_principal_entries = [
        {
            "work_item_id": str(entry.get("work_item_id", "")),
            "front_id": str(entry.get("front_id", "")),
            "reason": "PRINCIPAL_DECISION_IS_NOT_EXECUTION_AUTHORIZATION",
        }
        for entry in principal_brief.get("needs_you", []) or []
    ]
    result = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "source_snapshot_digest": snapshot_digest,
        "source_principal_brief_digest": str(principal_brief.get("brief_digest", "")),
        "packets": packets,
        "exceptions": exceptions,
        "ignored_principal_entries": ignored_principal_entries,
        "counts": {
            "packets": len(packets),
            "exceptions": len(exceptions),
            "ignored_principal_entries": len(ignored_principal_entries),
        },
    }
    result["plan_digest"] = _stable_digest(result)
    return result

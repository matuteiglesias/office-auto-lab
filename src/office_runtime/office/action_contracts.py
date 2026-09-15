"""Portable, evidence-backed Action contracts owned by Staff preparation."""

from __future__ import annotations

from typing import Any


ENTRY_SURFACE_TYPES = frozenset({"REPOSITORY", "CONTROL_STATE", "SUPPORT_ARTIFACT", "WORKFLOW", "CONNECTED_CONTEXT", "HUMAN_REVIEW"})
UNRESOLVED_DECISION_STATUSES = frozenset({"PENDING", "BLOCKED", "UNRESOLVED"})
GENERIC_OBJECTIVES = frozenset({"pull one bounded execution step with explicit acceptance evidence and stop after that unit completes."})


class ActionContractError(ValueError):
    pass


def validate_action_contract(value: Any, *, front_id: str) -> dict:
    """Validate substantive readiness without inventing an action unit."""
    if not isinstance(value, dict):
        raise ActionContractError("action contract is missing")
    contract = dict(value)
    required_text = ("objective", "why_now", "scope_boundary")
    for key in required_text:
        if not str(contract.get(key, "")).strip():
            raise ActionContractError(f"action contract is missing {key}")
    if str(contract["objective"]).strip().casefold() in GENERIC_OBJECTIVES:
        raise ActionContractError("action contract objective is generic")
    for key in ("acceptance_conditions", "stop_conditions", "expected_evidence"):
        values = contract.get(key)
        if not isinstance(values, list) or not values or not all(str(item).strip() for item in values):
            raise ActionContractError(f"action contract is missing {key}")
    for key in ("known_uncertainties", "decision_dependencies"):
        if not isinstance(contract.get(key, []), list):
            raise ActionContractError(f"action contract {key} must be a list")
    surface = contract.get("entry_surface")
    if not isinstance(surface, dict):
        raise ActionContractError("action contract is missing entry_surface")
    surface = dict(surface)
    surface_type = str(surface.get("type", "")).upper()
    if surface_type not in ENTRY_SURFACE_TYPES:
        raise ActionContractError("action contract has unsupported entry surface")
    requirements = {
        "REPOSITORY": ("repo_id", "workspace_id", "revision"),
        "CONTROL_STATE": ("table", "front_id"),
        "SUPPORT_ARTIFACT": ("artifact_id",),
        "WORKFLOW": ("workflow_ref", "operator_contract_id"),
        "CONNECTED_CONTEXT": ("source_ref",),
        "HUMAN_REVIEW": ("review_ref",),
    }
    for key in requirements[surface_type]:
        if not str(surface.get(key, "")).strip():
            raise ActionContractError(f"entry surface {surface_type} is missing {key}")
    if surface_type == "CONTROL_STATE" and str(surface.get("front_id", "")) != str(front_id):
        raise ActionContractError("control-state entry surface belongs to a different front")
    if "local_path" in surface or "path" in surface:
        raise ActionContractError("entry surface must not contain a machine-local path")
    contract["entry_surface"] = surface
    return contract


def unresolved_dependencies(contract: dict) -> list[str]:
    unresolved: list[str] = []
    for dependency in contract.get("decision_dependencies", []) or []:
        if not isinstance(dependency, dict):
            continue
        if str(dependency.get("status", "")).upper() in UNRESOLVED_DECISION_STATUSES:
            unresolved.append(str(dependency.get("decision_id", "")).strip() or "<unnamed>")
    return sorted(set(unresolved))

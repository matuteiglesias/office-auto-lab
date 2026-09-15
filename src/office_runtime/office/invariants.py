from __future__ import annotations

from typing import Iterable


class GenerationInvariantError(ValueError):
    pass


def _ids(rows: Iterable[dict], field: str) -> list[str]:
    return [str(row.get(field, "")).strip() for row in rows if str(row.get(field, "")).strip()]


def _assert_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise GenerationInvariantError(f"duplicate {label}")


def validate_forward_generation(
    snapshot: dict,
    work_set: dict,
    preparation: dict,
    principal: dict,
    execution: dict,
) -> list[str]:
    """Validate cross-layer invariants for one coherent Office v2 generation.

    Individual compilers already enforce their local contracts. This layer
    protects seams between them and catches accidental drift in later refactors.
    """
    snapshot_digest = str(snapshot.get("snapshot_digest", "")).strip()
    if not snapshot_digest:
        raise GenerationInvariantError("snapshot digest is required")

    lineage_digests = {
        str(work_set.get("source_snapshot_digest", "")).strip(),
        str(preparation.get("source_snapshot_digest", "")).strip(),
        str(principal.get("source_snapshot_digest", "")).strip(),
        str(execution.get("source_snapshot_digest", "")).strip(),
    }
    if lineage_digests != {snapshot_digest}:
        raise GenerationInvariantError("source snapshot digest diverged across forward layers")

    work_items = list(work_set.get("work_items", []) or [])
    work_ids = _ids(work_items, "work_item_id")
    _assert_unique(work_ids, "work_item_id")
    work_by_id = {str(row.get("work_item_id")): row for row in work_items}

    packets = list(preparation.get("packets", []) or [])
    staff_ids = _ids(packets, "work_item_id")
    _assert_unique(staff_ids, "Staff packet work_item_id")
    if set(staff_ids) != set(work_ids):
        raise GenerationInvariantError("Staff packets must cover the exact typed work set")
    packet_by_id = {str(row.get("work_item_id")): row for row in packets}

    sections = {
        "needs_you": list(principal.get("needs_you", []) or []),
        "ready_pulls": list(principal.get("ready_pulls", []) or []),
        "exceptions": list(principal.get("exceptions", []) or []),
        "moved_without_you": list(principal.get("moved_without_you", []) or []),
        "deferred_attention": list(principal.get("deferred_attention", []) or []),
    }
    principal_seen: set[str] = set()
    for section, rows in sections.items():
        ids = _ids(rows, "work_item_id")
        _assert_unique(ids, f"Principal {section} work_item_id")
        unknown = sorted(set(ids) - set(staff_ids))
        if unknown:
            raise GenerationInvariantError(f"Principal {section} references unknown work items: {unknown}")
        overlap = principal_seen.intersection(ids)
        if overlap:
            raise GenerationInvariantError(f"Principal work item appears in multiple sections: {sorted(overlap)}")
        principal_seen.update(ids)

    for row in sections["needs_you"]:
        work_id = str(row.get("work_item_id", ""))
        packet = packet_by_id[work_id]
        if not bool(packet.get("principal_needed")):
            raise GenerationInvariantError(f"needs_you item {work_id} was not prepared as principal-needed")
        if str(packet.get("preparation_status", "")).upper() not in {"PREPARED_DEEP", "PREPARED_LIGHT"}:
            raise GenerationInvariantError(f"needs_you item {work_id} is not prepared")

    for row in sections["ready_pulls"]:
        work_id = str(row.get("work_item_id", ""))
        packet = packet_by_id[work_id]
        if bool(packet.get("principal_needed")):
            raise GenerationInvariantError(f"ready pull {work_id} still requires principal judgment")
        if str(packet.get("preparation_status", "")).upper() not in {"PREPARED_DEEP", "PREPARED_LIGHT"}:
            raise GenerationInvariantError(f"ready pull {work_id} is not prepared")

    execution_packets = list(execution.get("packets", []) or [])
    execution_ids = _ids(execution_packets, "work_item_id")
    _assert_unique(execution_ids, "execution packet work_item_id")
    ready_ids = set(_ids(sections["ready_pulls"], "work_item_id"))
    if not set(execution_ids).issubset(ready_ids):
        raise GenerationInvariantError("execution packets may only originate from Principal ready pulls")

    for packet in execution_packets:
        work_id = str(packet.get("work_item_id", ""))
        kind = str(work_by_id.get(work_id, {}).get("kind", "")).upper()
        if kind == "DECIDE":
            raise GenerationInvariantError(f"DECIDE item {work_id} cannot become an execution packet")
        target = packet.get("target", {}) or {}
        for workspace in target.get("workspaces", []) or []:
            if str(workspace.get("status", "")).upper() != "RESOLVED":
                raise GenerationInvariantError(f"execution packet {work_id} has unresolved workspace identity")
        envelope = packet.get("operator", {}) or {}
        forbidden_effective = {"update_state", "open_work_items"}.intersection(envelope.get("effective_allowed_powers", []) or [])
        if forbidden_effective:
            raise GenerationInvariantError(f"execution packet {work_id} regained governance mutation powers")

    return [
        "one_snapshot_lineage",
        "unique_work_identity",
        "staff_exact_work_coverage",
        "principal_sections_are_disjoint",
        "principal_attention_is_prepared",
        "ready_pulls_require_no_principal_judgment",
        "execution_only_from_ready_pulls",
        "execution_identity_is_resolved",
        "execution_withholds_governance_mutation",
    ]

from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA_VERSION = "ops.principal-brief.v2"
KIND_RANK = {"DECIDE": 0, "UNBLOCK": 1, "VERIFY": 2, "EXECUTE": 3, "MAINTAIN": 4}
HORIZON_RANK = {"TODAY": 0, "THIS_WEEK": 1, "THIS_MONTH": 2, "MAINTENANCE": 3, "LATER": 4}
EXCEPTION_STATUSES = frozenset({"BLOCKED"})


class PrincipalCompileError(ValueError):
    pass


def _stable_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _priority(packet: dict) -> tuple[int, int, int, str]:
    state = packet.get("current_state", {}) or {}
    return (
        0 if packet.get("principal_needed") else 1,
        KIND_RANK.get(str(packet.get("kind", "")).upper(), 99),
        HORIZON_RANK.get(str(state.get("horizon", "")).upper(), 50),
        str(packet.get("work_item_id", "")),
    )


def _why_now(packet: dict) -> str:
    state = packet.get("current_state", {}) or {}
    needs = str(state.get("needs", "")).strip()
    if needs:
        return needs
    horizon = str(state.get("horizon", "")).strip()
    return f"This typed item is on the current {horizon or 'active'} pull frontier."


def _evidence_refs(packet: dict) -> list[dict]:
    refs: list[dict] = []
    for evidence in packet.get("evidence", []) or []:
        adapter = str(evidence.get("adapter", "")).strip()
        if adapter == "control_snapshot":
            runtime = evidence.get("runtime", {}) or {}
            if runtime.get("evidence_ref") or runtime.get("source_run_id"):
                refs.append({"kind": "runtime", "evidence_ref": runtime.get("evidence_ref", ""), "source_run_id": runtime.get("source_run_id", "")})
            for artifact in evidence.get("support_artifacts", []) or []:
                refs.append({"kind": "support_artifact", "artifact_id": artifact.get("artifact_id", ""), "uri": artifact.get("uri", ""), "authority_class": artifact.get("authority_class", "")})
        elif adapter == "local_repo":
            refs.append({"kind": "repository", "repo_id": evidence.get("repo_id", ""), "workspace_id": evidence.get("workspace_id", ""), "revision": evidence.get("revision", ""), "dirty": evidence.get("dirty")})
        else:
            refs.append({"kind": adapter or "evidence", "status": evidence.get("status", "")})
    return refs[:8]


def _base(packet: dict) -> dict:
    state = packet.get("current_state", {}) or {}
    entry = {
        "entry_id": str(packet.get("work_item_id", "")),
        "work_item_id": str(packet.get("work_item_id", "")),
        "front_id": str(packet.get("front_id", "")),
        "title": str(packet.get("title", "")),
        "kind": str(packet.get("kind", "")),
        "horizon": str(state.get("horizon", "")),
        "priority_mode": str(state.get("priority_mode", "")),
        "why_now": _why_now(packet),
        "recommended_move": str(packet.get("recommended_move", "")),
        "evidence_refs": _evidence_refs(packet),
        "staff_packet_id": str(packet.get("staff_packet_id", "")),
        "staff_packet_digest": str(packet.get("packet_digest", "")),
    }
    entry["entry_digest"] = _stable_digest(entry)
    return entry


def _is_exception(packet: dict) -> bool:
    status = str(packet.get("preparation_status", "")).upper()
    if status in EXCEPTION_STATUSES or packet.get("blockers"):
        return True
    return any(str(row.get("status", "")).lower() in {"blocked", "degraded", "error"} for row in packet.get("evidence", []) or [])


def _exception(packet: dict) -> dict:
    entry = _base(packet)
    status = str(packet.get("preparation_status", "")).upper()
    blockers = [str(value) for value in packet.get("blockers", []) or []]
    uncertainties = [str(value) for value in packet.get("uncertainties", []) or []]
    if status == "DEFERRED_BUDGET":
        code = "STAFF_PREP_BUDGET"
    elif blockers:
        code = "BLOCKED"
    else:
        code = "EVIDENCE_DEGRADED"
    entry.update({
        "exception_code": code,
        "preparation_status": status,
        "blockers": blockers,
        "uncertainties": uncertainties,
        "principal_attention_required": False,
    })
    entry["entry_digest"] = _stable_digest(entry)
    return entry


def _decision(packet: dict) -> dict:
    entry = _base(packet)
    entry.update({
        "question": str(packet.get("principal_question", "")).strip() or str(packet.get("question", "")).strip(),
        "recommended_default": str(packet.get("recommended_move", "")),
        "acceptable_outcomes": ["approve_default", "choose_narrower_alternative", "defer_with_review_point"],
        "decision_maturity": packet.get("decision_maturity", ""),
        "decision": packet.get("decision", {}),
    })
    entry["entry_digest"] = _stable_digest(entry)
    return entry


def _ready_pull(packet: dict) -> dict:
    entry = _base(packet)
    identity = packet.get("identity", {}) or {}
    entry.update({
        "entry_context": {"repo_ids": list(identity.get("repo_ids", []) or []), "workspace_states": list(identity.get("workspace_states", []) or [])},
        "preparation_status": packet.get("preparation_status", ""),
        "action_maturity": packet.get("action_maturity", ""),
        "action_contract": packet.get("action_contract", {}),
    })
    entry["entry_digest"] = _stable_digest(entry)
    return entry


def _minimal(packet: dict, reason: str) -> dict:
    return {"entry_id": str(packet.get("work_item_id", "")), "work_item_id": str(packet.get("work_item_id", "")), "front_id": str(packet.get("front_id", "")), "title": str(packet.get("title", "")), "kind": str(packet.get("kind", "")), "reason": reason}


def _compact_exceptions(exceptions: list[dict]) -> list[dict]:
    """Keep repeated typed symptoms visible without repeating one front."""
    grouped: dict[tuple[str, str], dict] = {}
    for entry in exceptions:
        key = (str(entry.get("front_id", "")), str(entry.get("exception_code", "")))
        if key not in grouped:
            grouped[key] = dict(entry)
            grouped[key]["work_item_ids"] = [str(entry.get("work_item_id", ""))]
            grouped[key]["kinds"] = [str(entry.get("kind", ""))]
            grouped[key]["blockers_by_work_item"] = {str(entry.get("work_item_id", "")): list(entry.get("blockers", []) or [])}
            grouped[key]["uncertainties_by_work_item"] = {str(entry.get("work_item_id", "")): list(entry.get("uncertainties", []) or [])}
            grouped[key]["all_blockers"] = list(entry.get("blockers", []) or [])
            grouped[key]["all_uncertainties"] = list(entry.get("uncertainties", []) or [])
            continue
        current = grouped[key]
        work_item_id = str(entry.get("work_item_id", ""))
        kind = str(entry.get("kind", ""))
        if work_item_id and work_item_id not in current["work_item_ids"]:
            current["work_item_ids"].append(work_item_id)
        if kind and kind not in current["kinds"]:
            current["kinds"].append(kind)
        current.setdefault("blockers_by_work_item", {})[work_item_id] = list(entry.get("blockers", []) or [])
        current.setdefault("uncertainties_by_work_item", {})[work_item_id] = list(entry.get("uncertainties", []) or [])
        for field, aggregate_field in (("blockers", "all_blockers"), ("uncertainties", "all_uncertainties")):
            values = current.setdefault(aggregate_field, [])
            for value in entry.get(field, []) or []:
                if value not in values:
                    values.append(value)
        current["entry_digest"] = _stable_digest(current)
    return list(grouped.values())


def _decision_is_mature(packet: dict) -> bool:
    if str(packet.get("kind", "")).upper() != "DECIDE":
        return False
    if str(packet.get("decision_maturity", "")).upper() != "READY_FOR_PRINCIPAL":
        return False
    decision = packet.get("decision", {}) or {}
    required = ("question", "recommendation", "options", "why_now", "consequence", "default_if_deferred", "post_decision_move")
    return all(decision.get(key) not in (None, "", []) for key in required)


def _materially_relevant_now(packet: dict) -> bool:
    state = packet.get("current_state", {}) or {}
    if str(state.get("carry_status", "")).upper() not in {"ACTIVE", "ACTIVE_LIGHT"}:
        return False
    return str(state.get("horizon", "")).upper() in {"TODAY", "THIS_WEEK"}


def _ready_for_pull(packet: dict) -> bool:
    return (
        str(packet.get("preparation_status", "")).upper() == "PREPARED_DEEP"
        and str(packet.get("action_maturity", "")).upper() == "READY_FOR_PULL"
        and str(packet.get("kind", "")).upper() in {"UNBLOCK", "VERIFY", "EXECUTE", "MAINTAIN"}
    )


def _section_ids(brief: dict, section: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in brief.get(section, []) or []:
        entry_id = str(row.get("entry_id", ""))
        if entry_id:
            out[entry_id] = str(row.get("entry_digest", ""))
    return out


def _delta(current: dict, previous: dict | None) -> dict:
    if not previous:
        return {
            "baseline": "none",
            "added": {section: [row.get("entry_id", "") for row in current.get(section, [])] for section in ("needs_you", "ready_pulls", "exceptions")},
            "cleared": {section: [] for section in ("needs_you", "ready_pulls", "exceptions")},
            "changed": {section: [] for section in ("needs_you", "ready_pulls", "exceptions")},
        }
    result = {"baseline": previous.get("brief_digest", ""), "added": {}, "cleared": {}, "changed": {}}
    for section in ("needs_you", "ready_pulls", "exceptions"):
        before = _section_ids(previous, section)
        after = _section_ids(current, section)
        result["added"][section] = sorted(set(after) - set(before))
        result["cleared"][section] = sorted(set(before) - set(after))
        result["changed"][section] = sorted(key for key in set(before).intersection(after) if before[key] != after[key])
    return result


def compile_principal_brief(preparation: dict, *, previous_brief: dict | None = None, max_needs_you: int = 3, max_ready_pulls: int = 3) -> dict:
    """Compress Staff preparation into the principal attention surface."""
    if max_needs_you < 0 or max_ready_pulls < 0:
        raise PrincipalCompileError("attention budgets must be non-negative")
    if str(preparation.get("schema_version", "")) != "ops.staff-preparation-set.v2":
        raise PrincipalCompileError("unsupported Staff preparation schema")
    source_snapshot_digest = str(preparation.get("source_snapshot_digest", "")).strip()
    if not source_snapshot_digest:
        raise PrincipalCompileError("Staff preparation is missing source snapshot digest")

    packets = [dict(packet) for packet in preparation.get("packets", [])]
    packets.sort(key=_priority)
    exceptions: list[dict] = []
    decision_candidates: list[dict] = []
    pull_candidates: list[dict] = []
    prepared_nonprincipal: list[dict] = []
    immature_decisions: list[dict] = []
    for packet in packets:
        if _is_exception(packet):
            exceptions.append(_exception(packet))
            continue
        if bool(packet.get("principal_needed")):
            if _decision_is_mature(packet) and _materially_relevant_now(packet):
                decision_candidates.append(packet)
            else:
                reason = "DECISION_NOT_READY" if str(packet.get("kind", "")).upper() == "DECIDE" else "PRINCIPAL_REQUIRED"
                immature_decisions.append(_minimal(packet, reason))
            continue
        if _ready_for_pull(packet):
            pull_candidates.append(packet)
            prepared_nonprincipal.append(packet)

    needs_you = [_decision(packet) for packet in decision_candidates[:max_needs_you]]
    deferred_attention = [_minimal(packet, "ATTENTION_BUDGET") for packet in decision_candidates[max_needs_you:]]
    ready_pulls = [_ready_pull(packet) for packet in pull_candidates[:max_ready_pulls]]
    ready_ids = {row["entry_id"] for row in ready_pulls}
    moved_without_you = [_minimal(packet, "STAFF_PREPARED") for packet in prepared_nonprincipal if str(packet.get("work_item_id", "")) not in ready_ids]
    preparation_counts = dict(preparation.get("counts", {}) or {})
    if "DEFERRED_BY_BUDGET" not in preparation_counts and "DEFERRED_BUDGET" not in preparation_counts:
        preparation_counts["DEFERRED_BY_BUDGET"] = sum(
            1 for packet in packets if str(packet.get("preparation_status", "")).upper() == "DEFERRED_BY_BUDGET"
        )
    principal_action_required = bool(needs_you)
    compacted_exceptions = _compact_exceptions(exceptions)
    brief = {
        "schema_version": SCHEMA_VERSION,
        "source_snapshot_digest": source_snapshot_digest,
        "source_preparation_digest": preparation.get("preparation_digest", ""),
        "needs_you": needs_you,
        "ready_pulls": ready_pulls,
        "exceptions": compacted_exceptions,
        "moved_without_you": moved_without_you,
        "deferred_attention": deferred_attention,
        "staff_follow_up": immature_decisions,
        "preparation_frontier": {
            "deep_prepared": preparation_counts.get("PREPARED_DEEP", 0),
            "deferred_by_budget": preparation_counts.get("DEFERRED_BY_BUDGET", preparation_counts.get("DEFERRED_BUDGET", 0)),
        },
        "principal_action_required": principal_action_required,
        "nothing_required": not principal_action_required,
        "counts": {"needs_you": len(needs_you), "ready_pulls": len(ready_pulls), "exceptions": len(compacted_exceptions), "moved_without_you": len(moved_without_you), "deferred_attention": len(deferred_attention), "staff_follow_up": len(immature_decisions)},
    }
    brief["delta"] = _delta(brief, previous_brief)
    brief["brief_digest"] = _stable_digest(brief)
    return brief


def render_principal_markdown(brief: dict) -> str:
    lines = ["# Principal Brief", ""]
    if brief.get("nothing_required"):
        lines += ["**No principal action required.**", ""]
    else:
        lines += ["## Needs you", ""]
        for row in brief.get("needs_you", []) or []:
            lines.append(f"- **{row.get('title') or row.get('front_id')}** — {row.get('question')}")
            if row.get("recommended_default"):
                lines.append(f"  - Default: {row.get('recommended_default')}")
        for row in brief.get("deferred_attention", []) or []:
            lines.append(f"- Deferred by attention budget: {row.get('title') or row.get('front_id')}")
        lines.append("")
    lines += ["## Ready pulls", ""]
    if brief.get("ready_pulls"):
        for row in brief["ready_pulls"]:
            lines.append(f"- **{row.get('title') or row.get('front_id')}** — {row.get('recommended_move')}")
    else:
        lines.append("- None.")
    lines += ["", "## Exceptions", ""]
    if brief.get("exceptions"):
        for row in brief["exceptions"]:
            detail = "; ".join(row.get("blockers", []) or row.get("uncertainties", []))
            lines.append(f"- **{row.get('title') or row.get('front_id')}** — {row.get('exception_code')}{': ' + detail if detail else ''}")
    else:
        lines.append("- None.")
    lines += ["", "## Moved without you", ""]
    if brief.get("moved_without_you"):
        for row in brief["moved_without_you"]:
            lines.append(f"- {row.get('title') or row.get('front_id')} — Staff prepared.")
    else:
        lines.append("- None.")
    delta = brief.get("delta", {}) or {}
    lines += ["", "## Since last brief", ""]
    if delta.get("baseline") == "none":
        lines.append("- First v2 Principal baseline.")
    else:
        changes = sum(len(delta.get(bucket, {}).get(section, [])) for bucket in ("added", "cleared", "changed") for section in ("needs_you", "ready_pulls", "exceptions"))
        lines.append(f"- {changes} material section changes.")
    lines.append("")
    return "\n".join(lines)

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


RECEIPT_SCHEMA_VERSION = "ops.execution-receipt.v2"
CLOSURE_SET_SCHEMA_VERSION = "ops.closure-set.v2"
PROPOSAL_SCHEMA_VERSION = "ops.reentry-proposal.v2"
RECEIPT_STATUSES = frozenset({"COMPLETED", "PARTIAL", "BLOCKED", "NO_CHANGE", "FAILED"})


class ReentryCompileError(ValueError):
    pass


def _stable_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _as_list(value: Any, field: str) -> list:
    if not isinstance(value, list):
        raise ReentryCompileError(f"{field} must be a list")
    return value


def _nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ReentryCompileError(f"{field} must be non-empty")
    return text


def _packet_index(execution_plan: dict) -> dict[str, dict]:
    packets = execution_plan.get("packets", [])
    if not isinstance(packets, list):
        raise ReentryCompileError("execution plan packets must be a list")
    out: dict[str, dict] = {}
    for raw in packets:
        packet = dict(raw)
        packet_id = _nonempty(packet.get("execution_packet_id"), "execution_packet_id")
        if packet_id in out:
            raise ReentryCompileError(f"duplicate execution packet id {packet_id!r}")
        out[packet_id] = packet
    return out


def validate_receipt(raw: dict, packet: dict, source_snapshot_digest: str) -> dict:
    if str(raw.get("schema_version", "")) != RECEIPT_SCHEMA_VERSION:
        raise ReentryCompileError("unsupported execution receipt schema")
    receipt_id = _nonempty(raw.get("receipt_id"), "receipt_id")
    packet_id = _nonempty(raw.get("execution_packet_id"), "execution_packet_id")
    if packet_id != str(packet.get("execution_packet_id", "")):
        raise ReentryCompileError(f"receipt {receipt_id!r} references the wrong execution packet")
    packet_digest = _nonempty(raw.get("execution_packet_digest"), "execution_packet_digest")
    if packet_digest != str(packet.get("packet_digest", "")):
        raise ReentryCompileError(f"receipt {receipt_id!r} packet digest mismatch")
    snapshot_digest = _nonempty(raw.get("source_snapshot_digest"), "source_snapshot_digest")
    if snapshot_digest != source_snapshot_digest or snapshot_digest != str(packet.get("source_snapshot_digest", "")):
        raise ReentryCompileError(f"receipt {receipt_id!r} snapshot digest mismatch")
    work_item_id = _nonempty(raw.get("work_item_id"), "work_item_id")
    front_id = _nonempty(raw.get("front_id"), "front_id")
    if work_item_id != str(packet.get("work_item_id", "")) or front_id != str(packet.get("front_id", "")):
        raise ReentryCompileError(f"receipt {receipt_id!r} work/front identity mismatch")

    status = str(raw.get("status", "")).strip().upper()
    if status not in RECEIPT_STATUSES:
        raise ReentryCompileError(f"receipt {receipt_id!r} has unsupported status {status!r}")
    actions_taken = _as_list(raw.get("actions_taken", []), "actions_taken")
    evidence = _as_list(raw.get("evidence", []), "evidence")
    residuals = _as_list(raw.get("residuals", []), "residuals")
    blockers = _as_list(raw.get("blockers", []), "blockers")
    acceptance_results = _as_list(raw.get("acceptance_results", []), "acceptance_results")

    expected = list(packet.get("acceptance_conditions", []) or [])
    by_condition: dict[str, dict] = {}
    for result in acceptance_results:
        if not isinstance(result, dict):
            raise ReentryCompileError("acceptance_results entries must be objects")
        condition = _nonempty(result.get("condition"), "acceptance_results.condition")
        if condition in by_condition:
            raise ReentryCompileError(f"receipt {receipt_id!r} duplicates acceptance result {condition!r}")
        if not isinstance(result.get("passed"), bool):
            raise ReentryCompileError("acceptance_results.passed must be boolean")
        by_condition[condition] = dict(result)

    unknown_conditions = sorted(set(by_condition) - set(expected))
    if unknown_conditions:
        raise ReentryCompileError(f"receipt {receipt_id!r} reports unknown acceptance conditions: {unknown_conditions}")
    if status == "COMPLETED":
        missing = [condition for condition in expected if condition not in by_condition]
        failed = [condition for condition, result in by_condition.items() if not result["passed"]]
        if missing or failed:
            raise ReentryCompileError(
                f"COMPLETED receipt {receipt_id!r} must pass every packet acceptance condition; missing={missing}, failed={failed}"
            )
        if not evidence:
            raise ReentryCompileError(f"COMPLETED receipt {receipt_id!r} must contain evidence")
    if status in {"BLOCKED", "FAILED"} and not blockers:
        raise ReentryCompileError(f"{status} receipt {receipt_id!r} must name at least one blocker")

    normalized = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "execution_packet_id": packet_id,
        "execution_packet_digest": packet_digest,
        "work_item_id": work_item_id,
        "front_id": front_id,
        "kind": str(packet.get("kind", "")),
        "status": status,
        "started_at": str(raw.get("started_at", "")).strip(),
        "finished_at": str(raw.get("finished_at", "")).strip(),
        "actions_taken": actions_taken,
        "evidence": evidence,
        "acceptance_results": [by_condition[condition] for condition in expected if condition in by_condition],
        "residuals": residuals,
        "blockers": blockers,
        "suggested_next_touch": str(raw.get("suggested_next_touch", "")).strip(),
        "source_snapshot_digest": snapshot_digest,
    }
    normalized["receipt_digest"] = _stable_digest(normalized)
    return normalized


def _classification(receipt: dict) -> str:
    status = receipt["status"]
    if status == "COMPLETED" and not receipt["residuals"]:
        return "DONE"
    if status in {"COMPLETED", "PARTIAL"}:
        return "FOLLOW_UP"
    if status in {"BLOCKED", "NO_CHANGE", "FAILED"}:
        return "WAITING"
    return "REVIEW"


def _what_became_true(receipt: dict) -> str:
    if receipt["status"] == "COMPLETED":
        return "The bounded execution packet completed with all acceptance conditions passing."
    if receipt["status"] == "PARTIAL":
        return "The bounded execution packet produced partial evidence but did not close all intended work."
    if receipt["status"] == "BLOCKED":
        return "Execution reached an explicit blocker and stopped without widening scope."
    if receipt["status"] == "FAILED":
        return "Execution failed and left an explicit blocker/evidence trail."
    return "Execution produced no material state change and stopped."


def _proposal(receipt: dict) -> dict:
    classification = _classification(receipt)
    what_remains = list(receipt["residuals"])
    if receipt["blockers"]:
        what_remains.extend(receipt["blockers"])
    proposal = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "proposal_id": "rp:" + receipt["receipt_id"],
        "front_id": receipt["front_id"],
        "work_item_id": receipt["work_item_id"],
        "execution_packet_id": receipt["execution_packet_id"],
        "receipt_id": receipt["receipt_id"],
        "classification": classification,
        "what_became_true": _what_became_true(receipt),
        "what_remains": what_remains,
        "suggested_next_touch": receipt["suggested_next_touch"],
        "evidence": list(receipt["evidence"]),
        "reentry_intent": {
            "review_closure": True,
            "review_follow_up": classification in {"FOLLOW_UP", "WAITING"},
            "review_carry_state": True,
        },
        "candidate_control_patch": None,
        "mutation_performed": False,
        "source_snapshot_digest": receipt["source_snapshot_digest"],
        "source_receipt_digest": receipt["receipt_digest"],
    }
    proposal["proposal_digest"] = _stable_digest(proposal)
    return proposal


def compile_reentry_v2(snapshot: dict, execution_plan: dict, receipts: Iterable[dict]) -> dict:
    """Validate execution receipts and produce non-mutating closure/reentry proposals."""
    snapshot_digest = _nonempty(snapshot.get("snapshot_digest"), "snapshot_digest")
    if str(execution_plan.get("schema_version", "")) != "ops.execution-plan.v2":
        raise ReentryCompileError("unsupported execution plan schema")
    if str(execution_plan.get("source_snapshot_digest", "")).strip() != snapshot_digest:
        raise ReentryCompileError("execution plan does not belong to the supplied Control Tower snapshot")

    packets = _packet_index(execution_plan)
    normalized: list[dict] = []
    seen_receipts: set[str] = set()
    seen_packets: set[str] = set()
    for raw in receipts:
        if not isinstance(raw, dict):
            raise ReentryCompileError("each receipt must be an object")
        packet_id = _nonempty(raw.get("execution_packet_id"), "execution_packet_id")
        packet = packets.get(packet_id)
        if packet is None:
            raise ReentryCompileError(f"receipt references unknown execution packet {packet_id!r}")
        receipt = validate_receipt(raw, packet, snapshot_digest)
        if receipt["receipt_id"] in seen_receipts:
            raise ReentryCompileError(f"duplicate receipt_id {receipt['receipt_id']!r}")
        if packet_id in seen_packets:
            raise ReentryCompileError(f"multiple receipts supplied for execution packet {packet_id!r}")
        seen_receipts.add(receipt["receipt_id"])
        seen_packets.add(packet_id)
        normalized.append(receipt)

    normalized.sort(key=lambda row: (row["front_id"], row["execution_packet_id"]))
    proposals = [_proposal(receipt) for receipt in normalized]
    unclosed = [
        {
            "execution_packet_id": packet_id,
            "work_item_id": str(packet.get("work_item_id", "")),
            "front_id": str(packet.get("front_id", "")),
            "status": "OPEN_NO_RECEIPT",
        }
        for packet_id, packet in sorted(packets.items())
        if packet_id not in seen_packets
    ]
    result = {
        "schema_version": CLOSURE_SET_SCHEMA_VERSION,
        "source_snapshot_digest": snapshot_digest,
        "source_execution_plan_digest": str(execution_plan.get("plan_digest", "")),
        "receipts": normalized,
        "proposals": proposals,
        "unclosed_packets": unclosed,
        "mutation_performed": False,
        "counts": {
            "receipts": len(normalized),
            "proposals": len(proposals),
            "done": sum(row["classification"] == "DONE" for row in proposals),
            "follow_up": sum(row["classification"] == "FOLLOW_UP" for row in proposals),
            "waiting": sum(row["classification"] == "WAITING" for row in proposals),
            "unclosed_packets": len(unclosed),
        },
    }
    result["closure_set_digest"] = _stable_digest(result)
    return result

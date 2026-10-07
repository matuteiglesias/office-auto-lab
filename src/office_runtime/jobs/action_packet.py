from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

INPUT_CONTRACT = "ops.job-action-input@1"
OUTPUT_CONTRACT = "ops.job-action-packet@1"

_CLOSED_MARKERS = {
    "rejected",
    "closed",
    "closed_or_stale",
    "expired_filled",
    "withdrawn",
}

def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _require_text(mapping: dict[str, Any], key: str, *, allow_blank: bool = False) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    value = value.strip()
    if not allow_blank and not value:
        raise ValueError(f"{key} must not be blank")
    return value


def _optional_date(mapping: dict[str, Any], key: str) -> date | None:
    value = mapping.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be YYYY-MM-DD") from exc


def _contact_state(enrichment: dict[str, Any]) -> str:
    contact = _require_mapping(enrichment.get("contact", {}), "enrichment.contact")
    route = str(contact.get("route") or "").strip()
    last_touch = str(enrichment.get("last_external_touch_on") or "").strip()
    if route and last_touch:
        return "warm"
    if route:
        return "known"
    return "none"


def _packet_blocker(packet_state: str) -> str | None:
    if packet_state.startswith("missing_"):
        return packet_state.removeprefix("missing_").replace("_", " ")
    if packet_state.startswith("prepare_"):
        return packet_state.replace("_", " ")
    return None


def compile_packet(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("contract") != INPUT_CONTRACT:
        raise ValueError(f"contract must be {INPUT_CONTRACT}")

    as_of_text = _require_text(payload, "as_of")
    try:
        as_of = date.fromisoformat(as_of_text)
    except ValueError as exc:
        raise ValueError("as_of must be YYYY-MM-DD") from exc

    agenda = _require_mapping(payload.get("agenda"), "agenda")
    if agenda.get("agenda_id") != "job-search":
        raise ValueError("agenda.agenda_id must be job-search")
    orientation_state = _require_text(agenda, "orientation_state")
    if orientation_state not in {"orientation-ready", "refresh-needed"}:
        raise ValueError("agenda.orientation_state is unsupported")

    job = _require_mapping(payload.get("job"), "job")
    job_id = _require_text(job, "id")
    company = _require_text(job, "company")
    role = _require_text(job, "role")
    process_status = _require_text(job, "process_status")
    next_action = _require_text(job, "next_action_min")
    decision = _require_text(job, "decision", allow_blank=True)

    enrichment = _require_mapping(payload.get("enrichment"), "enrichment")
    packet_state = _require_text(enrichment, "packet_state")
    action_due = _optional_date(enrichment, "action_due_on")
    followup_due = _optional_date(enrichment, "followup_due_on")
    last_touch = _optional_date(enrichment, "last_external_touch_on")
    material_base = _require_text(enrichment, "material_base", allow_blank=True)
    contact = _require_mapping(enrichment.get("contact", {}), "enrichment.contact")
    contact_name = str(contact.get("name") or "").strip()
    contact_route = str(contact.get("route") or "").strip()

    if orientation_state == "refresh-needed":
        action_state = "blocked_orientation"
        why_now = "Job Search Agenda requires refresh before this packet can be trusted."
        blocker = "stale orientation"
        stop_condition = "Refresh the Job Search Agenda from ATS and current process evidence."
    else:
        closed = (
            process_status in _CLOSED_MARKERS
            or packet_state.startswith("closed")
            or decision.lower().startswith(("drop", "close"))
        )
        if closed:
            action_state = "closed"
            why_now = "The current application path is closed."
            blocker = None
            stop_condition = (
                "Do no more application work; preserve only an explicitly dated "
                "relationship follow-up when useful."
            )
        elif action_due is not None and action_due <= as_of:
            action_state = "urgent_action"
            why_now = f"Action is due by {action_due.isoformat()}."
            blocker = _packet_blocker(packet_state)
            stop_condition = "Advance, submit, or explicitly decline before the action window passes."
        elif followup_due is not None and followup_due <= as_of:
            action_state = "followup_due"
            why_now = f"Follow-up is due by {followup_due.isoformat()}."
            blocker = None if contact_route else "no contact route"
            stop_condition = "Send one bounded follow-up or record why no follow-up is appropriate."
        elif packet_state.startswith("missing_") or packet_state.startswith("prepare_"):
            action_state = "prepare_packet"
            why_now = "The opportunity is live but the application packet is not ready."
            blocker = _packet_blocker(packet_state)
            stop_condition = "Stop preparing once the minimum role-specific packet is ready to submit."
        elif packet_state.startswith("ready"):
            action_state = "ready_to_apply"
            why_now = "The opportunity and base materials are ready for an application block."
            blocker = None
            stop_condition = "Submit or explicitly defer/drop; do not return to broad discovery first."
        elif "waiting" in process_status:
            action_state = "waiting"
            why_now = "The process is externally waiting and no dated follow-up is due yet."
            blocker = "external response or scheduling"
            stop_condition = "Do not recreate application work while waiting; act only on new evidence or due follow-up."
        else:
            action_state = "review"
            why_now = "The row is active but lacks a stronger deterministic action signal."
            blocker = _packet_blocker(packet_state)
            stop_condition = "Resolve the next action or explicitly downgrade the row."

    return {
        "contract": OUTPUT_CONTRACT,
        "as_of": as_of_text,
        "agenda": {
            "agenda_id": "job-search",
            "orientation_state": orientation_state,
            "source_sha256": agenda.get("source_sha256"),
        },
        "job": {
            "id": job_id,
            "company": company,
            "role": role,
            "process_status": process_status,
            "decision": decision,
            "posting_url": job.get("posting_url"),
        },
        "action": {
            "state": action_state,
            "why_now": why_now,
            "blocker": blocker,
            "next_block": next_action,
            "stop_condition": stop_condition,
        },
        "contact": {
            "state": _contact_state(enrichment),
            "name": contact_name or None,
            "route": contact_route or None,
        },
        "materials": {
            "packet_state": packet_state,
            "material_base": material_base or None,
        },
        "dates": {
            "action_due_on": action_due.isoformat() if action_due else None,
            "followup_due_on": followup_due.isoformat() if followup_due else None,
            "last_external_touch_on": last_touch.isoformat() if last_touch else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    packet = compile_packet(payload)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

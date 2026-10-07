"""Deterministic, read-only job-search action packet compiler.

The compiler consumes normalized evidence prepared from canonical/live sources.
It never queries ATS, Gmail, Contacts, Calendar, CRM, or the web directly and
never mutates application state.  ATS remains canonical for job/application
state; communication/contact/calendar evidence only explains the next action.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

CONTRACT = "artifact:ops.job-action-packet@1"
READY_STATUSES = {"ready_deadline", "ready_to_apply", "ready_not_applied"}
WAITING_SCHEDULE_STATUSES = {
    "availability_submitted_waiting_schedule",
    "waiting_schedule",
}
CLOSED_STATUSES = {"rejected", "expired_filled", "withdrawn", "closed"}


class JobPacketError(ValueError):
    pass


def _iso_date(value: Any, *, field: str, required: bool = False) -> date | None:
    if value in (None, ""):
        if required:
            raise JobPacketError(f"{field} is required")
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise JobPacketError(f"{field} must be YYYY-MM-DD") from exc


def _business_days_after(start: date, end: date) -> int:
    if end <= start:
        return 0
    count = 0
    cursor = start + timedelta(days=1)
    while cursor <= end:
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)
    return count


def _normalize_refs(items: list[dict[str, Any]], kind: str) -> list[str]:
    refs: list[str] = []
    for item in items:
        ref = item.get("evidence_ref")
        if not isinstance(ref, str) or not ref.strip():
            raise JobPacketError(f"{kind} evidence_ref is required")
        refs.append(ref)
    return sorted(set(refs))


def _verified_contacts(contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accepted = []
    for item in contacts:
        state = item.get("verification")
        if state not in {
            "process-email",
            "ats-named+gmail",
            "crm-verified",
            "organization-channel",
        }:
            continue
        accepted.append(
            {
                "name": item.get("name"),
                "email": item.get("email"),
                "role": item.get("role"),
                "verification": state,
                "evidence_ref": item.get("evidence_ref"),
            }
        )
    accepted.sort(
        key=lambda item: (
            item["verification"] == "organization-channel",
            str(item.get("name") or ""),
            str(item.get("email") or ""),
        )
    )
    return accepted


def _contact_packet(
    ats: dict[str, Any],
    contacts: list[dict[str, Any]],
) -> dict[str, Any]:
    verified = _verified_contacts(contacts)
    personal = [
        item for item in verified
        if item["verification"] != "organization-channel"
    ]
    org_channels = [
        item for item in verified
        if item["verification"] == "organization-channel"
    ]
    contact_recommended = bool(ats.get("source_contact")) or (
        str(ats.get("source_type", "")).lower().startswith("recruiter")
        or "warm" in str(ats.get("source_type", "")).lower()
    )

    if personal:
        state = "verified-person"
        primary = personal[0]
    elif org_channels:
        state = "organization-channel"
        primary = org_channels[0]
    elif contact_recommended:
        state = "unresolved-recommended"
        primary = None
    else:
        state = "none-needed"
        primary = None

    return {
        "state": state,
        "contact_recommended": contact_recommended,
        "primary": primary,
        "alternatives": verified[1:] if primary else verified,
    }


def _latest_outbound(communications: list[dict[str, Any]]) -> dict[str, Any] | None:
    outbound = [
        item for item in communications
        if item.get("direction") == "outbound" and item.get("date")
    ]
    if not outbound:
        return None
    return max(outbound, key=lambda item: str(item["date"]))


def _future_calendar(
    calendar: list[dict[str, Any]],
    as_of: date,
) -> list[dict[str, Any]]:
    future = []
    for item in calendar:
        event_date = _iso_date(item.get("date"), field="calendar.date")
        if event_date and event_date >= as_of and item.get("status") != "cancelled":
            future.append(item)
    return sorted(future, key=lambda item: str(item["date"]))


def _follow_up(
    *,
    ats: dict[str, Any],
    communications: list[dict[str, Any]],
    calendar: list[dict[str, Any]],
    contact: dict[str, Any],
    as_of: date,
) -> dict[str, Any]:
    process_status = str(ats.get("process_status") or "")
    status_updated = _iso_date(
        ats.get("status_updated_on"),
        field="ats.status_updated_on",
    )
    future_events = _future_calendar(calendar, as_of)
    last_outbound = _latest_outbound(communications)

    if process_status in READY_STATUSES:
        return {
            "state": "blocked-on-application",
            "due_on": None,
            "reason": "Application has not yet been submitted.",
            "channel": None,
        }

    if process_status in WAITING_SCHEDULE_STATUSES:
        if future_events:
            return {
                "state": "scheduled",
                "due_on": None,
                "reason": "A future interview/calendar event is already present.",
                "channel": None,
            }
        if status_updated and _business_days_after(status_updated, as_of) >= 2:
            channel = (
                "email"
                if contact.get("state") in {"verified-person", "organization-channel"}
                else "resolve-contact"
            )
            return {
                "state": "due",
                "due_on": as_of.isoformat(),
                "reason": "Availability/process handoff has waited at least two business days with no future calendar event.",
                "channel": channel,
            }
        due_on = None
        if status_updated:
            cursor = status_updated
            remaining = 2
            while remaining:
                cursor += timedelta(days=1)
                if cursor.weekday() < 5:
                    remaining -= 1
            due_on = cursor.isoformat()
        return {
            "state": "waiting",
            "due_on": due_on,
            "reason": "Waiting window has not yet crossed the two-business-day follow-up threshold.",
            "channel": None,
        }

    if process_status == "rejected":
        if last_outbound and str(last_outbound.get("purpose")) in {
            "feedback-request",
            "relationship-close",
        }:
            return {
                "state": "waiting-response",
                "due_on": None,
                "reason": "A bounded post-process message has already been sent.",
                "channel": None,
            }
        next_action = str(ats.get("next_action_min") or "").lower()
        if "feedback" in next_action or "reply" in next_action:
            return {
                "state": "due",
                "due_on": as_of.isoformat(),
                "reason": "ATS explicitly asks for a bounded feedback/relationship follow-up.",
                "channel": (
                    "email"
                    if contact.get("state") == "verified-person"
                    else "resolve-contact"
                ),
            }
        return {
            "state": "not-applicable",
            "due_on": None,
            "reason": "Closed process has no explicit residual follow-up action.",
            "channel": None,
        }

    if process_status in CLOSED_STATUSES:
        return {
            "state": "not-applicable",
            "due_on": None,
            "reason": "Process is closed.",
            "channel": None,
        }

    return {
        "state": "review",
        "due_on": None,
        "reason": "No deterministic follow-up rule matches this process status.",
        "channel": None,
    }


def compile_action_packet(
    snapshot: dict[str, Any],
    *,
    as_of: str,
) -> dict[str, Any]:
    observed = _iso_date(as_of, field="as_of", required=True)
    assert observed is not None

    ats = snapshot.get("ats")
    if not isinstance(ats, dict):
        raise JobPacketError("snapshot.ats must be an object")

    job_id = ats.get("id")
    company = ats.get("company")
    role = ats.get("role")
    if not all(isinstance(value, str) and value.strip() for value in (job_id, company, role)):
        raise JobPacketError("ATS id, company, and role are required")

    communications = snapshot.get("communications") or []
    contacts = snapshot.get("contacts") or []
    calendar = snapshot.get("calendar") or []
    materials = snapshot.get("materials") or {}
    if not all(isinstance(value, list) for value in (communications, contacts, calendar)):
        raise JobPacketError("communications, contacts, and calendar must be lists")
    if not isinstance(materials, dict):
        raise JobPacketError("materials must be an object")

    contact = _contact_packet(ats, contacts)
    follow_up = _follow_up(
        ats=ats,
        communications=communications,
        calendar=calendar,
        contact=contact,
        as_of=observed,
    )

    required = sorted(set(str(x) for x in materials.get("required", []) if str(x)))
    available = sorted(set(str(x) for x in materials.get("available", []) if str(x)))
    missing = sorted(set(required) - set(available))
    deadline = _iso_date(ats.get("deadline"), field="ats.deadline")
    process_status = str(ats.get("process_status") or "")

    if deadline and deadline < observed and process_status not in CLOSED_STATUSES:
        action_class = "DEADLINE_MISSED_REVIEW"
        urgency = "critical"
    elif deadline and deadline <= observed + timedelta(days=1) and process_status in READY_STATUSES:
        action_class = "APPLY_NOW"
        urgency = "critical"
    elif process_status in READY_STATUSES:
        action_class = "PREPARE_APPLICATION"
        urgency = "high" if deadline else "normal"
    elif follow_up["state"] == "due":
        action_class = "FOLLOW_UP"
        urgency = "high"
    elif process_status == "rejected":
        action_class = "CLOSE_OR_WAIT_FEEDBACK"
        urgency = "low"
    elif process_status in WAITING_SCHEDULE_STATUSES:
        action_class = "WAIT_PROCESS"
        urgency = "normal"
    else:
        action_class = "REVIEW"
        urgency = "normal"

    warnings: list[str] = []
    if contact["state"] == "unresolved-recommended":
        warnings.append("A contact is recommended by ATS/process context but no process-verified contact evidence was supplied.")
    if missing and process_status in READY_STATUSES:
        warnings.append("Application is not packet-ready because required materials are missing.")
    if process_status in READY_STATUSES and ats.get("decision") and "apply" in str(ats.get("decision")).lower() and ats.get("submitted") is True:
        warnings.append("ATS says submitted=true while process_status still describes a pre-application state; reconcile canonical ATS state.")

    next_block = str(ats.get("next_action_min") or "").strip()
    if process_status in READY_STATUSES and missing:
        next_block = f"Prepare missing material(s): {', '.join(missing)}. " + next_block
    elif follow_up["state"] == "due":
        next_block = "Send one bounded process follow-up. " + next_block

    stop_condition = str(snapshot.get("stop_condition") or "").strip()
    if not stop_condition:
        if process_status in CLOSED_STATUSES:
            stop_condition = "No further effort unless a new explicit opportunity or response reopens the process."
        elif process_status in READY_STATUSES:
            stop_condition = "Stop preparation once the complete application packet is ready for explicit submission."
        else:
            stop_condition = "Stop after the next bounded action or when fresh process evidence changes state."

    packet = {
        "contract": CONTRACT,
        "as_of": as_of,
        "job": {
            "id": job_id,
            "company": company,
            "role": role,
            "posting_url": ats.get("posting_url"),
            "location_mode": ats.get("location_mode"),
            "fit_level": ats.get("fit_level"),
            "decision": ats.get("decision"),
            "process_status": process_status,
            "deadline": deadline.isoformat() if deadline else None,
        },
        "action": {
            "class": action_class,
            "urgency": urgency,
            "current_blocker": snapshot.get("current_blocker"),
            "next_block": next_block,
            "stop_condition": stop_condition,
        },
        "preparation": {
            "required_materials": required,
            "available_materials": available,
            "missing_materials": missing,
            "application_packet_ready": process_status in READY_STATUSES and not missing,
            "evidence_to_reuse": sorted(set(str(x) for x in snapshot.get("evidence_to_reuse", []) if str(x))),
        },
        "contact": contact,
        "follow_up": follow_up,
        "evidence": {
            "ats_ref": snapshot.get("ats_ref"),
            "communication_refs": _normalize_refs(communications, "communication"),
            "contact_refs": _normalize_refs(contacts, "contact"),
            "calendar_refs": _normalize_refs(calendar, "calendar"),
        },
        "warnings": warnings,
    }
    return packet

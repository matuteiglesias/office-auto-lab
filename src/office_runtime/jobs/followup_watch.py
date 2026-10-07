"""Aggregate per-job packets into a quiet follow-up/deadline attention watch."""

from __future__ import annotations

import hashlib
import json
from typing import Any

CONTRACT = "artifact:ops.job-followup-watch@1"


class JobWatchError(ValueError):
    pass


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compile_followup_watch(
    *,
    action_packets: list[dict[str, Any]],
    prep_packets: list[dict[str, Any]] | None,
    previous_fingerprints: dict[str, str] | None,
    as_of: str,
) -> dict[str, Any]:
    if not isinstance(action_packets, list):
        raise JobWatchError("action_packets must be a list")
    previous_fingerprints = previous_fingerprints or {}
    prep_by_job = {
        str(packet.get("job_ref")): packet
        for packet in (prep_packets or [])
        if packet.get("job_ref")
    }

    attention: list[dict[str, Any]] = []
    fingerprints: dict[str, str] = {}
    for packet in action_packets:
        job = packet.get("job")
        action = packet.get("action")
        follow_up = packet.get("follow_up")
        if not isinstance(job, dict) or not isinstance(action, dict) or not isinstance(follow_up, dict):
            raise JobWatchError("invalid action packet shape")
        job_id = str(job.get("id") or "").strip()
        if not job_id:
            raise JobWatchError("action packet job.id is required")

        reasons: list[str] = []
        severity = "normal"
        action_class = action.get("class")
        urgency = action.get("urgency")
        if action_class == "FOLLOW_UP" and follow_up.get("state") == "due":
            reasons.append("process-follow-up-due")
            severity = "high"
        if action_class in {"APPLY_NOW", "DEADLINE_MISSED_REVIEW"}:
            reasons.append("application-deadline")
            severity = "critical"

        job_ref = f"ats:2026:{job_id}"
        prep = prep_by_job.get(job_ref)
        if (
            prep
            and prep.get("ready_for_submission_materially") is False
            and urgency in {"critical", "high"}
        ):
            reasons.append("application-material-blocker")
            if urgency == "critical":
                severity = "critical"
            elif severity != "critical":
                severity = "high"

        state_payload = {
            "job_id": job_id,
            "process_status": job.get("process_status"),
            "action_class": action_class,
            "urgency": urgency,
            "follow_up_state": follow_up.get("state"),
            "follow_up_due_on": follow_up.get("due_on"),
            "deadline": job.get("deadline"),
            "action_due_on": job.get("action_due_on"),
            "followup_due_on": job.get("followup_due_on"),
            "reasons": sorted(reasons),
            "prep_ready": prep.get("ready_for_submission_materially") if prep else None,
            "prep_states": (
                sorted(
                    (item.get("requirement_id"), item.get("state"))
                    for item in prep.get("requirements", [])
                )
                if prep
                else []
            ),
        }
        fingerprint = _fingerprint(state_payload)
        fingerprints[job_id] = fingerprint

        if not reasons:
            continue
        if previous_fingerprints.get(job_id) == fingerprint:
            continue

        attention.append(
            {
                "job_id": job_id,
                "company": job.get("company"),
                "role": job.get("role"),
                "severity": severity,
                "reasons": sorted(reasons),
                "verified_contact": packet.get("contact", {}).get("primary"),
                "next_block": action.get("next_block"),
                "stop_condition": action.get("stop_condition"),
                "fingerprint": fingerprint,
            }
        )

    severity_rank = {"critical": 0, "high": 1, "normal": 2}
    attention.sort(key=lambda item: (severity_rank[item["severity"]], item["job_id"]))
    return {
        "contract": CONTRACT,
        "as_of": as_of,
        "notify": bool(attention),
        "attention": attention,
        "fingerprints": fingerprints,
        "suppression": "Repeat notifications require a changed deterministic fingerprint.",
    }

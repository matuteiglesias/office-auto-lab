from __future__ import annotations

from office_runtime.jobs import JobPacketError, compile_action_packet


def _base(job_id: str, company: str, role: str, process_status: str) -> dict:
    return {
        "ats": {
            "id": job_id,
            "company": company,
            "role": role,
            "process_status": process_status,
            "decision": "Continue",
            "source_type": "Job posting",
            "source_contact": "",
            "next_action_min": "",
        },
        "ats_ref": f"ats:2026:{job_id}",
        "communications": [],
        "contacts": [],
        "calendar": [],
        "materials": {"required": [], "available": []},
        "evidence_to_reuse": [],
    }


def test_beon_rejection_with_feedback_already_sent_waits() -> None:
    snapshot = _base("JOB-209", "BEON.tech", "Data Engineer (Python)", "rejected")
    snapshot["ats"].update(
        {
            "source_type": "Recruiter inbound",
            "source_contact": "Florencia Vasquez",
            "next_action_min": "Reply asking for the main deciding factor or gap.",
            "status_updated_on": "2026-10-07",
        }
    )
    snapshot["contacts"] = [
        {
            "name": "Florencia Vasquez",
            "email": "florencia.vasquez@beon.tech",
            "role": "IT Recruiter",
            "verification": "process-email",
            "evidence_ref": "gmail:beon:feedback",
        }
    ]
    snapshot["communications"] = [
        {
            "direction": "outbound",
            "date": "2026-10-07",
            "purpose": "feedback-request",
            "evidence_ref": "gmail:beon:reply",
        }
    ]

    packet = compile_action_packet(snapshot, as_of="2026-10-07")

    assert packet["contact"]["state"] == "verified-person"
    assert packet["follow_up"]["state"] == "waiting-response"
    assert packet["action"]["class"] == "CLOSE_OR_WAIT_FEEDBACK"


def test_telus_waiting_schedule_becomes_due_after_two_business_days() -> None:
    snapshot = _base("JOB-210", "TELUS Digital", "Senior Data Scientist", "availability_submitted_waiting_schedule")
    snapshot["ats"].update(
        {
            "source_type": "Recruiter process",
            "source_contact": "Gabrielly Oliveira / Delfina Heilmann",
            "status_updated_on": "2026-10-05",
            "next_action_min": "Follow up if still unscheduled.",
        }
    )
    snapshot["contacts"] = [
        {
            "name": "Gabrielly Oliveira",
            "email": "gabrielly.oliveira@poatek.com",
            "role": "Recruiter",
            "verification": "process-email",
            "evidence_ref": "gmail:telus:availability-request",
        },
        {
            "name": "Delfina Heilmann",
            "email": "delfina.heilmann@gm2dev.com",
            "role": "Recruiter",
            "verification": "process-email",
            "evidence_ref": "gmail:telus:prior-process",
        },
    ]

    packet = compile_action_packet(snapshot, as_of="2026-10-07")

    assert packet["follow_up"]["state"] == "due"
    assert packet["follow_up"]["channel"] == "email"
    assert packet["action"]["class"] == "FOLLOW_UP"


def test_telus_future_interview_suppresses_follow_up() -> None:
    snapshot = _base("JOB-210", "TELUS Digital", "Senior Data Scientist", "availability_submitted_waiting_schedule")
    snapshot["ats"]["status_updated_on"] = "2026-10-05"
    snapshot["calendar"] = [
        {
            "date": "2026-10-09",
            "status": "confirmed",
            "evidence_ref": "calendar:telus:skills-interview",
        }
    ]

    packet = compile_action_packet(snapshot, as_of="2026-10-07")

    assert packet["follow_up"]["state"] == "scheduled"
    assert packet["action"]["class"] == "WAIT_PROCESS"


def test_zs_ready_not_applied_keeps_application_and_relationship_distinct() -> None:
    snapshot = _base("JOB-211", "ZS", "Data Science Lead", "ready_not_applied")
    snapshot["ats"].update(
        {
            "source_type": "Job posting + warm contact",
            "source_contact": "Tina Martinez",
            "decision": "Prepare strong application",
            "next_action_min": "Finish the polished role-specific CV, then submit.",
        }
    )
    snapshot["contacts"] = [
        {
            "name": "Tina Martinez",
            "email": "tina.martinez@zs.com",
            "role": "Talent Acquisition",
            "verification": "ats-named+gmail",
            "evidence_ref": "gmail:zs:tina",
        }
    ]
    snapshot["materials"] = {
        "required": ["role-specific CV"],
        "available": [],
    }

    packet = compile_action_packet(snapshot, as_of="2026-10-07")

    assert packet["contact"]["state"] == "verified-person"
    assert packet["follow_up"]["state"] == "blocked-on-application"
    assert packet["preparation"]["application_packet_ready"] is False
    assert packet["preparation"]["missing_materials"] == ["role-specific CV"]
    assert packet["action"]["class"] == "PREPARE_APPLICATION"


def test_unicef_deadline_packet_requires_materials_without_inventing_person() -> None:
    snapshot = _base("JOB-213", "UNICEF", "REACH Process Reengineering Consultant", "ready_deadline")
    snapshot["ats"].update(
        {
            "deadline": "2026-10-08",
            "decision": "Go/no-go and apply",
            "next_action_min": "Complete the application before the deadline.",
        }
    )
    snapshot["contacts"] = [
        {
            "name": None,
            "email": "contratacionesargentina@unicef.org",
            "role": "organizational channel",
            "verification": "organization-channel",
            "evidence_ref": "contacts:unicef:org-channel",
        }
    ]
    snapshot["materials"] = {
        "required": ["CV", "cover letter", "financial proposal"],
        "available": ["CV"],
    }

    packet = compile_action_packet(snapshot, as_of="2026-10-07")

    assert packet["action"]["class"] == "APPLY_NOW"
    assert packet["action"]["urgency"] == "critical"
    assert packet["contact"]["state"] == "organization-channel"
    assert packet["preparation"]["missing_materials"] == ["cover letter", "financial proposal"]


def test_fractal_direct_application_does_not_block_on_missing_contact() -> None:
    snapshot = _base("JOB-214", "Fractal River", "Data Engineer", "ready_to_apply")
    snapshot["ats"].update(
        {
            "decision": "Apply",
            "next_action_min": "Prepare salary answer and concise client-facing cover letter.",
        }
    )
    snapshot["materials"] = {
        "required": ["Data/AI Engineering CV", "cover letter", "desired salary"],
        "available": ["Data/AI Engineering CV"],
    }

    packet = compile_action_packet(snapshot, as_of="2026-10-07")

    assert packet["contact"]["state"] == "none-needed"
    assert packet["follow_up"]["state"] == "blocked-on-application"
    assert packet["preparation"]["missing_materials"] == ["cover letter", "desired salary"]


def test_unverified_same_name_contact_is_not_promoted() -> None:
    snapshot = _base("JOB-X", "ExampleCo", "Senior Role", "ready_to_apply")
    snapshot["ats"].update(
        {
            "source_type": "Recruiter process",
            "source_contact": "Alex Example",
        }
    )
    snapshot["contacts"] = [
        {
            "name": "Alex Example",
            "email": "alex@old-company.example",
            "role": "Recruiter",
            "verification": "name-only",
            "evidence_ref": "contacts:alex:old",
        }
    ]

    packet = compile_action_packet(snapshot, as_of="2026-10-07")

    assert packet["contact"]["state"] == "unresolved-recommended"
    assert packet["contact"]["primary"] is None
    assert packet["warnings"]


def test_invalid_evidence_without_ref_fails_closed() -> None:
    snapshot = _base("JOB-X", "ExampleCo", "Role", "ready_to_apply")
    snapshot["contacts"] = [{"name": "Someone", "verification": "process-email"}]

    try:
        compile_action_packet(snapshot, as_of="2026-10-07")
    except JobPacketError as exc:
        assert "evidence_ref" in str(exc)
    else:
        raise AssertionError("missing evidence_ref must fail closed")

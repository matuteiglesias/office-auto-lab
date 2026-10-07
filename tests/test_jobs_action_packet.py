from __future__ import annotations

import unittest

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


class JobActionPacketTests(unittest.TestCase):
    def test_rejection_with_feedback_already_sent_waits(self) -> None:
        snapshot = _base("JOB-209", "ExampleCo", "Data Engineer", "rejected")
        snapshot["ats"].update(
            {
                "source_type": "Recruiter inbound",
                "source_contact": "Recruiter One",
                "next_action_min": "Reply asking for the main deciding factor or gap.",
                "status_updated_on": "2026-10-07",
            }
        )
        snapshot["contacts"] = [
            {
                "name": "Recruiter One",
                "email": "recruiter.one@example.com",
                "role": "IT Recruiter",
                "verification": "process-email",
                "evidence_ref": "gmail:example:feedback",
            }
        ]
        snapshot["communications"] = [
            {
                "direction": "outbound",
                "date": "2026-10-07",
                "purpose": "feedback-request",
                "evidence_ref": "gmail:example:reply",
            }
        ]

        packet = compile_action_packet(snapshot, as_of="2026-10-07")

        self.assertEqual(packet["contact"]["state"], "verified-person")
        self.assertEqual(packet["follow_up"]["state"], "waiting-response")
        self.assertEqual(packet["action"]["class"], "CLOSE_OR_WAIT_FEEDBACK")

    def test_waiting_schedule_becomes_due_after_two_business_days(self) -> None:
        snapshot = _base(
            "JOB-210",
            "ExampleCo",
            "Senior Data Scientist",
            "availability_submitted_waiting_schedule",
        )
        snapshot["ats"].update(
            {
                "source_type": "Recruiter process",
                "source_contact": "Recruiter One / Recruiter Two",
                "status_updated_on": "2026-10-05",
                "next_action_min": "Follow up if still unscheduled.",
            }
        )
        snapshot["contacts"] = [
            {
                "name": "Recruiter One",
                "email": "recruiter.one@example.com",
                "role": "Recruiter",
                "verification": "process-email",
                "evidence_ref": "gmail:example:availability-request",
            },
            {
                "name": "Recruiter Two",
                "email": "recruiter.two@example.com",
                "role": "Recruiter",
                "verification": "process-email",
                "evidence_ref": "gmail:example:prior-process",
            },
        ]

        packet = compile_action_packet(snapshot, as_of="2026-10-07")

        self.assertEqual(packet["follow_up"]["state"], "due")
        self.assertEqual(packet["follow_up"]["channel"], "email")
        self.assertEqual(packet["action"]["class"], "FOLLOW_UP")

    def test_future_interview_suppresses_follow_up(self) -> None:
        snapshot = _base(
            "JOB-210",
            "ExampleCo",
            "Senior Data Scientist",
            "availability_submitted_waiting_schedule",
        )
        snapshot["ats"]["status_updated_on"] = "2026-10-05"
        snapshot["calendar"] = [
            {
                "date": "2026-10-09",
                "status": "confirmed",
                "evidence_ref": "calendar:example:skills-interview",
            }
        ]

        packet = compile_action_packet(snapshot, as_of="2026-10-07")

        self.assertEqual(packet["follow_up"]["state"], "scheduled")
        self.assertEqual(packet["action"]["class"], "WAIT_PROCESS")

    def test_explicit_waiting_followup_date_controls_due_state(self) -> None:
        snapshot = _base(
            "JOB-210",
            "ExampleCo",
            "Senior Data Scientist",
            "availability_submitted_waiting_schedule",
        )
        snapshot["ats"].update(
            {
                "status_updated_on": "2026-10-05",
                "followup_due_on": "2026-10-10",
            }
        )
        snapshot["contacts"] = [
            {
                "name": "Recruiter One",
                "email": "recruiter.one@example.com",
                "role": "Recruiter",
                "verification": "process-email",
                "evidence_ref": "gmail:example:process",
            }
        ]

        before = compile_action_packet(snapshot, as_of="2026-10-09")
        due = compile_action_packet(snapshot, as_of="2026-10-10")

        self.assertEqual(before["follow_up"]["state"], "waiting")
        self.assertEqual(before["follow_up"]["due_on"], "2026-10-10")
        self.assertEqual(due["follow_up"]["state"], "due")
        self.assertEqual(due["follow_up"]["due_on"], "2026-10-10")

    def test_calendar_suppresses_explicit_waiting_followup(self) -> None:
        snapshot = _base(
            "JOB-210",
            "ExampleCo",
            "Senior Data Scientist",
            "availability_submitted_waiting_schedule",
        )
        snapshot["ats"]["followup_due_on"] = "2026-10-07"
        snapshot["calendar"] = [
            {
                "date": "2026-10-09",
                "status": "confirmed",
                "evidence_ref": "calendar:example:interview",
            }
        ]

        packet = compile_action_packet(snapshot, as_of="2026-10-07")

        self.assertEqual(packet["follow_up"]["state"], "scheduled")
        self.assertIsNone(packet["follow_up"]["due_on"])

    def test_rejected_feedback_waits_until_explicit_residual_followup(self) -> None:
        snapshot = _base("JOB-209", "ExampleCo", "Data Engineer", "rejected")
        snapshot["ats"].update(
            {
                "followup_due_on": "2026-10-14",
                "source_type": "Recruiter inbound",
                "source_contact": "Recruiter One",
            }
        )
        snapshot["contacts"] = [
            {
                "name": "Recruiter One",
                "email": "recruiter.one@example.com",
                "role": "Recruiter",
                "verification": "process-email",
                "evidence_ref": "gmail:example:contact",
            }
        ]
        snapshot["communications"] = [
            {
                "direction": "outbound",
                "date": "2026-10-07",
                "purpose": "feedback-request",
                "evidence_ref": "gmail:example:feedback",
            }
        ]

        waiting = compile_action_packet(snapshot, as_of="2026-10-07")
        due = compile_action_packet(snapshot, as_of="2026-10-14")

        self.assertEqual(waiting["follow_up"]["state"], "waiting-response")
        self.assertEqual(waiting["follow_up"]["due_on"], "2026-10-14")
        self.assertEqual(due["follow_up"]["state"], "due")
        self.assertEqual(due["action"]["class"], "FOLLOW_UP")

    def test_calendar_suppresses_rejected_residual_followup(self) -> None:
        snapshot = _base("JOB-209", "ExampleCo", "Data Engineer", "rejected")
        snapshot["ats"]["followup_due_on"] = "2026-10-14"
        snapshot["communications"] = [
            {
                "direction": "outbound",
                "date": "2026-10-07",
                "purpose": "feedback-request",
                "evidence_ref": "gmail:example:feedback",
            }
        ]
        snapshot["calendar"] = [
            {
                "date": "2026-10-15",
                "status": "confirmed",
                "evidence_ref": "calendar:example:followup-call",
            }
        ]

        packet = compile_action_packet(snapshot, as_of="2026-10-14")

        self.assertEqual(packet["follow_up"]["state"], "scheduled")

    def test_ready_not_applied_keeps_application_and_relationship_distinct(self) -> None:
        snapshot = _base("JOB-211", "ExampleCo", "Data Science Lead", "ready_not_applied")
        snapshot["ats"].update(
            {
                "source_type": "Job posting + warm contact",
                "source_contact": "Recruiter One",
                "decision": "Prepare strong application",
                "next_action_min": "Finish the polished role-specific CV, then submit.",
            }
        )
        snapshot["contacts"] = [
            {
                "name": "Recruiter One",
                "email": "recruiter.one@example.com",
                "role": "Talent Acquisition",
                "verification": "ats-named+gmail",
                "evidence_ref": "gmail:example:recruiter",
            }
        ]
        snapshot["materials"] = {
            "required": ["role-specific CV"],
            "available": [],
        }

        packet = compile_action_packet(snapshot, as_of="2026-10-07")

        self.assertEqual(packet["contact"]["state"], "verified-person")
        self.assertEqual(packet["follow_up"]["state"], "blocked-on-application")
        self.assertFalse(packet["preparation"]["application_packet_ready"])
        self.assertEqual(
            packet["preparation"]["missing_materials"],
            ["role-specific CV"],
        )
        self.assertEqual(packet["action"]["class"], "PREPARE_APPLICATION")

    def test_deadline_packet_requires_materials_without_inventing_person(self) -> None:
        snapshot = _base("JOB-213", "ExampleOrg", "Process Consultant", "ready_deadline")
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
                "email": "applications@example.org",
                "role": "organizational channel",
                "verification": "organization-channel",
                "evidence_ref": "contacts:example:org-channel",
            }
        ]
        snapshot["materials"] = {
            "required": ["CV", "cover letter", "financial proposal"],
            "available": ["CV"],
        }

        packet = compile_action_packet(snapshot, as_of="2026-10-07")

        self.assertEqual(packet["action"]["class"], "APPLY_NOW")
        self.assertEqual(packet["action"]["urgency"], "critical")
        self.assertEqual(packet["contact"]["state"], "organization-channel")
        self.assertEqual(
            packet["preparation"]["missing_materials"],
            ["cover letter", "financial proposal"],
        )

    def test_direct_application_does_not_block_on_missing_contact(self) -> None:
        snapshot = _base("JOB-214", "ExampleCo", "Data Engineer", "ready_to_apply")
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

        self.assertEqual(packet["contact"]["state"], "none-needed")
        self.assertEqual(packet["follow_up"]["state"], "blocked-on-application")
        self.assertEqual(
            packet["preparation"]["missing_materials"],
            ["cover letter", "desired salary"],
        )

    def test_unverified_same_name_contact_is_not_promoted(self) -> None:
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

        self.assertEqual(packet["contact"]["state"], "unresolved-recommended")
        self.assertIsNone(packet["contact"]["primary"])
        self.assertTrue(packet["warnings"])

    def test_invalid_evidence_without_ref_fails_closed(self) -> None:
        snapshot = _base("JOB-X", "ExampleCo", "Role", "ready_to_apply")
        snapshot["contacts"] = [
            {"name": "Someone", "verification": "process-email"}
        ]

        with self.assertRaisesRegex(JobPacketError, "evidence_ref"):
            compile_action_packet(snapshot, as_of="2026-10-07")


if __name__ == "__main__":
    unittest.main()

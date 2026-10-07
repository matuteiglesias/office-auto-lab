import unittest

from office_runtime.jobs.action_packet import (
    INPUT_CONTRACT,
    OUTPUT_CONTRACT,
    compile_packet,
)


def base_payload() -> dict:
    return {
        "contract": INPUT_CONTRACT,
        "as_of": "2026-10-07",
        "agenda": {
            "agenda_id": "job-search",
            "orientation_state": "orientation-ready",
            "source_sha256": "abc",
        },
        "job": {
            "id": "JOB-1",
            "company": "Example",
            "role": "Senior Data Scientist",
            "process_status": "ready_to_apply",
            "decision": "Apply",
            "next_action_min": "Tailor and submit.",
            "posting_url": "https://example.com/job",
        },
        "enrichment": {
            "action_due_on": "",
            "followup_due_on": "",
            "last_external_touch_on": "",
            "packet_state": "ready_tailor_and_apply",
            "material_base": "base-cv.pdf",
            "contact": {"name": "", "route": ""},
        },
    }


class JobActionPacketTests(unittest.TestCase):
    def test_ready_to_apply(self) -> None:
        packet = compile_packet(base_payload())
        self.assertEqual(packet["contract"], OUTPUT_CONTRACT)
        self.assertEqual(packet["action"]["state"], "ready_to_apply")
        self.assertEqual(packet["contact"]["state"], "none")

    def test_deadline_beats_packet_preparation(self) -> None:
        payload = base_payload()
        payload["enrichment"]["action_due_on"] = "2026-10-08"
        payload["enrichment"]["packet_state"] = "missing_cover_letter_financial_proposal"
        payload["as_of"] = "2026-10-08"
        packet = compile_packet(payload)
        self.assertEqual(packet["action"]["state"], "urgent_action")
        self.assertEqual(packet["action"]["blocker"], "cover letter financial proposal")

    def test_followup_due_with_warm_contact(self) -> None:
        payload = base_payload()
        payload["job"]["process_status"] = "availability_submitted_waiting_schedule"
        payload["enrichment"]["packet_state"] = "waiting_schedule"
        payload["enrichment"]["followup_due_on"] = "2026-10-07"
        payload["enrichment"]["last_external_touch_on"] = "2026-10-05"
        payload["enrichment"]["contact"] = {
            "name": "Recruiter",
            "route": "email: recruiter@example.com",
        }
        packet = compile_packet(payload)
        self.assertEqual(packet["action"]["state"], "followup_due")
        self.assertEqual(packet["contact"]["state"], "warm")

    def test_followup_beats_generic_action_due(self) -> None:
        payload = base_payload()
        payload["job"]["process_status"] = "availability_submitted_waiting_schedule"
        payload["enrichment"]["packet_state"] = "waiting_schedule"
        payload["enrichment"]["action_due_on"] = "2026-10-07"
        payload["enrichment"]["followup_due_on"] = "2026-10-07"
        payload["enrichment"]["contact"] = {
            "name": "Recruiter",
            "route": "email: recruiter@example.com",
        }
        packet = compile_packet(payload)
        self.assertEqual(packet["action"]["state"], "followup_due")

    def test_closed_path_can_surface_relationship_followup(self) -> None:
        payload = base_payload()
        payload["as_of"] = "2026-10-14"
        payload["job"]["process_status"] = "rejected"
        payload["job"]["decision"] = "Close current search / keep relationship warm"
        payload["enrichment"]["packet_state"] = "closed_followup"
        payload["enrichment"]["followup_due_on"] = "2026-10-14"
        payload["enrichment"]["contact"] = {
            "name": "Recruiter",
            "route": "email: recruiter@example.com",
        }
        packet = compile_packet(payload)
        self.assertEqual(packet["action"]["state"], "followup_due")
        self.assertIn("closed", packet["action"]["why_now"])

    def test_prepare_packet(self) -> None:
        payload = base_payload()
        payload["job"]["process_status"] = "ready_not_applied"
        payload["enrichment"]["packet_state"] = "prepare_cv_then_apply"
        packet = compile_packet(payload)
        self.assertEqual(packet["action"]["state"], "prepare_packet")
        self.assertEqual(packet["action"]["blocker"], "prepare cv then apply")

    def test_closed_path(self) -> None:
        payload = base_payload()
        payload["job"]["process_status"] = "rejected"
        payload["job"]["decision"] = "Close current search / keep relationship warm"
        payload["enrichment"]["packet_state"] = "closed_followup"
        packet = compile_packet(payload)
        self.assertEqual(packet["action"]["state"], "closed")

    def test_refresh_needed_blocks_packet(self) -> None:
        payload = base_payload()
        payload["agenda"]["orientation_state"] = "refresh-needed"
        packet = compile_packet(payload)
        self.assertEqual(packet["action"]["state"], "blocked_orientation")

    def test_rejects_wrong_agenda(self) -> None:
        payload = base_payload()
        payload["agenda"]["agenda_id"] = "media-monitor"
        with self.assertRaisesRegex(ValueError, "job-search"):
            compile_packet(payload)


if __name__ == "__main__":
    unittest.main()

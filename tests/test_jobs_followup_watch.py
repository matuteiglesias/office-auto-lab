from __future__ import annotations

import unittest

from office_runtime.jobs import JobWatchError, compile_followup_watch


def _action(
    job_id: str,
    company: str,
    action_class: str,
    urgency: str,
    follow_state: str,
    *,
    deadline: str | None = None,
    action_due_on: str | None = None,
    followup_due_on: str | None = None,
) -> dict:
    return {
        "job": {
            "id": job_id,
            "company": company,
            "role": "Role",
            "process_status": "active",
            "deadline": deadline,
            "action_due_on": action_due_on,
            "followup_due_on": followup_due_on,
        },
        "action": {
            "class": action_class,
            "urgency": urgency,
            "next_block": f"Next for {job_id}",
            "stop_condition": f"Stop for {job_id}",
        },
        "follow_up": {
            "state": follow_state,
            "due_on": followup_due_on if follow_state == "due" else None,
        },
        "contact": {
            "primary": (
                {"name": "Recruiter", "email": "recruiter@example.com"}
                if job_id == "JOB-210"
                else None
            )
        },
    }


class JobFollowupWatchTests(unittest.TestCase):
    def test_surfaces_due_followup_and_immediate_deadline_only(self) -> None:
        actions = [
            _action(
                "JOB-209",
                "ExampleCo",
                "CLOSE_OR_WAIT_FEEDBACK",
                "low",
                "waiting-response",
                followup_due_on="2026-10-14",
            ),
            _action(
                "JOB-210",
                "ExampleCo",
                "FOLLOW_UP",
                "high",
                "due",
                followup_due_on="2026-10-07",
            ),
            _action(
                "JOB-211",
                "ExampleCo",
                "PREPARE_APPLICATION",
                "normal",
                "blocked-on-application",
            ),
            _action(
                "JOB-213",
                "ExampleOrg",
                "APPLY_NOW",
                "critical",
                "blocked-on-application",
                action_due_on="2026-10-08",
            ),
        ]
        prep = [
            {
                "job_ref": "ats:2026:JOB-211",
                "ready_for_submission_materially": False,
                "requirements": [
                    {"requirement_id": "cv", "state": "review-required"}
                ],
            },
            {
                "job_ref": "ats:2026:JOB-213",
                "ready_for_submission_materially": False,
                "requirements": [
                    {"requirement_id": "cv", "state": "review-required"},
                    {
                        "requirement_id": "financial-proposal",
                        "state": "missing-known",
                    },
                ],
            },
        ]

        watch = compile_followup_watch(
            action_packets=actions,
            prep_packets=prep,
            previous_fingerprints={},
            as_of="2026-10-07",
        )

        self.assertTrue(watch["notify"])
        self.assertEqual(
            [item["job_id"] for item in watch["attention"]],
            ["JOB-213", "JOB-210"],
        )
        unicef = watch["attention"][0]
        self.assertEqual(unicef["severity"], "critical")
        self.assertEqual(
            unicef["reasons"],
            ["application-deadline", "application-material-blocker"],
        )
        telus = watch["attention"][1]
        self.assertEqual(telus["reasons"], ["process-follow-up-due"])
        self.assertEqual(
            telus["verified_contact"]["email"],
            "recruiter@example.com",
        )

    def test_unchanged_attention_is_suppressed_by_fingerprint(self) -> None:
        actions = [
            _action(
                "JOB-210",
                "ExampleCo",
                "FOLLOW_UP",
                "high",
                "due",
                followup_due_on="2026-10-07",
            )
        ]
        first = compile_followup_watch(
            action_packets=actions,
            prep_packets=[],
            previous_fingerprints={},
            as_of="2026-10-07",
        )
        second = compile_followup_watch(
            action_packets=actions,
            prep_packets=[],
            previous_fingerprints=first["fingerprints"],
            as_of="2026-10-07",
        )

        self.assertTrue(first["notify"])
        self.assertFalse(second["notify"])
        self.assertEqual(second["attention"], [])

    def test_normal_priority_material_gap_does_not_nag(self) -> None:
        actions = [
            _action(
                "JOB-211",
                "ExampleCo",
                "PREPARE_APPLICATION",
                "normal",
                "blocked-on-application",
            )
        ]
        prep = [
            {
                "job_ref": "ats:2026:JOB-211",
                "ready_for_submission_materially": False,
                "requirements": [
                    {"requirement_id": "cv", "state": "review-required"}
                ],
            }
        ]

        watch = compile_followup_watch(
            action_packets=actions,
            prep_packets=prep,
            previous_fingerprints={},
            as_of="2026-10-07",
        )

        self.assertFalse(watch["notify"])

    def test_changed_canonical_due_date_rearms_notification(self) -> None:
        first_packet = _action(
            "JOB-210",
            "ExampleCo",
            "FOLLOW_UP",
            "high",
            "due",
            followup_due_on="2026-10-07",
        )
        first = compile_followup_watch(
            action_packets=[first_packet],
            prep_packets=[],
            previous_fingerprints={},
            as_of="2026-10-07",
        )

        changed_packet = _action(
            "JOB-210",
            "ExampleCo",
            "FOLLOW_UP",
            "high",
            "due",
            followup_due_on="2026-10-08",
        )
        second = compile_followup_watch(
            action_packets=[changed_packet],
            prep_packets=[],
            previous_fingerprints=first["fingerprints"],
            as_of="2026-10-08",
        )

        self.assertNotEqual(
            first["fingerprints"]["JOB-210"],
            second["fingerprints"]["JOB-210"],
        )
        self.assertTrue(second["notify"])

    def test_invalid_action_packet_shape_fails_closed(self) -> None:
        with self.assertRaisesRegex(JobWatchError, "invalid action packet shape"):
            compile_followup_watch(
                action_packets=[{"job": {"id": "JOB-X"}}],
                prep_packets=[],
                previous_fingerprints={},
                as_of="2026-10-07",
            )


if __name__ == "__main__":
    unittest.main()

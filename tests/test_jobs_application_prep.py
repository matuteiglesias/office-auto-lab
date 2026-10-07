from __future__ import annotations

import unittest

from office_runtime.jobs import JobPrepError, compile_application_prep


REGISTRY = [
    {
        "asset_id": "CV_GENERIC_EN_2026",
        "asset_type": "cv",
        "track": "Data/AI general",
        "language": "en",
        "status": "candidate_needs_review",
        "title": "generic-cv.pdf",
        "url": "drive:cv-generic",
        "last_reviewed": "2026-10-07",
    },
    {
        "asset_id": "COVER_LETTER_REFERENCE_EN",
        "asset_type": "cover_letter_reference",
        "track": "general",
        "language": "en",
        "status": "reference_only",
        "title": "Cover Letter Template — Reference",
        "url": "drive:cover-reference",
        "last_reviewed": "2026-10-07",
    },
    {
        "asset_id": "CV_DATA_AI_ENGINEER_EN",
        "asset_type": "cv",
        "track": "Data & AI Engineering",
        "language": "en",
        "status": "missing",
    },
    {
        "asset_id": "CV_DATA_SCIENCE_EN",
        "asset_type": "cv",
        "track": "Data Science / Applied ML",
        "language": "en",
        "status": "missing",
    },
    {
        "asset_id": "CV_INSTITUTIONAL_CONSULTING_EN",
        "asset_type": "cv",
        "track": "Institutional / consulting",
        "language": "en",
        "status": "missing",
    },
    {
        "asset_id": "FINANCIAL_PROPOSAL_TEMPLATE",
        "asset_type": "financial_proposal",
        "track": "Institutional / consulting",
        "language": "en",
        "status": "missing",
    },
]


class JobApplicationPrepTests(unittest.TestCase):
    def test_data_science_uses_generic_cv_only_as_review_required_fallback(self) -> None:
        packet = compile_application_prep(
            job_ref="ats:2026:JOB-211",
            requirements=[
                {
                    "requirement_id": "role-specific-cv",
                    "label": "Role-specific CV",
                    "accepted_asset_types": ["cv"],
                    "track": "Data Science / Applied ML",
                    "language": "en",
                    "allow_general_base": True,
                }
            ],
            asset_registry=REGISTRY,
            as_of="2026-10-07",
        )

        self.assertFalse(packet["ready_for_submission_materially"])
        req = packet["requirements"][0]
        self.assertEqual(req["state"], "review-required")
        self.assertEqual(
            req["selected_asset"]["asset_id"],
            "CV_GENERIC_EN_2026",
        )
        self.assertEqual(
            req["known_missing_assets"],
            ["CV_DATA_SCIENCE_EN"],
        )

    def test_engineering_exposes_cv_review_and_cover_letter_reference(self) -> None:
        packet = compile_application_prep(
            job_ref="ats:2026:JOB-214",
            requirements=[
                {
                    "requirement_id": "role-specific-cv",
                    "accepted_asset_types": ["cv"],
                    "track": "Data & AI Engineering",
                    "language": "en",
                    "allow_general_base": True,
                },
                {
                    "requirement_id": "cover-letter",
                    "accepted_asset_types": [
                        "cover_letter",
                        "cover_letter_reference",
                    ],
                    "track": "general",
                    "language": "en",
                    "allow_general_base": True,
                },
            ],
            asset_registry=REGISTRY,
            as_of="2026-10-07",
        )

        states = {
            item["requirement_id"]: item["state"]
            for item in packet["requirements"]
        }
        self.assertEqual(
            states,
            {
                "role-specific-cv": "review-required",
                "cover-letter": "draft-from-reference",
            },
        )
        self.assertFalse(packet["ready_for_submission_materially"])

    def test_institutional_application_exposes_three_distinct_material_gaps(self) -> None:
        packet = compile_application_prep(
            job_ref="ats:2026:JOB-213",
            requirements=[
                {
                    "requirement_id": "institutional-cv",
                    "accepted_asset_types": ["cv"],
                    "track": "Institutional / consulting",
                    "language": "en",
                    "allow_general_base": True,
                },
                {
                    "requirement_id": "cover-letter",
                    "accepted_asset_types": [
                        "cover_letter",
                        "cover_letter_reference",
                    ],
                    "track": "general",
                    "language": "en",
                    "allow_general_base": True,
                },
                {
                    "requirement_id": "financial-proposal",
                    "accepted_asset_types": ["financial_proposal"],
                    "track": "Institutional / consulting",
                    "language": "en",
                    "allow_general_base": False,
                },
            ],
            asset_registry=REGISTRY,
            as_of="2026-10-07",
        )

        states = {
            item["requirement_id"]: item["state"]
            for item in packet["requirements"]
        }
        self.assertEqual(states["institutional-cv"], "review-required")
        self.assertEqual(states["cover-letter"], "draft-from-reference")
        self.assertEqual(states["financial-proposal"], "missing-known")
        self.assertFalse(packet["ready_for_submission_materially"])

    def test_approved_exact_track_beats_generic_candidate(self) -> None:
        registry = REGISTRY + [
            {
                "asset_id": "CV_DS_APPROVED",
                "asset_type": "cv",
                "track": "Data Science / Applied ML",
                "language": "en",
                "status": "approved_current",
                "title": "CV DS",
                "url": "drive:cv-ds",
                "last_reviewed": "2026-10-07",
            }
        ]
        packet = compile_application_prep(
            job_ref="ats:2026:JOB-211",
            requirements=[
                {
                    "requirement_id": "cv",
                    "accepted_asset_types": ["cv"],
                    "track": "Data Science / Applied ML",
                    "language": "en",
                    "allow_general_base": True,
                }
            ],
            asset_registry=registry,
            as_of="2026-10-07",
        )

        self.assertTrue(packet["ready_for_submission_materially"])
        self.assertEqual(
            packet["requirements"][0]["selected_asset"]["asset_id"],
            "CV_DS_APPROVED",
        )

    def test_duplicate_asset_ids_fail_closed(self) -> None:
        with self.assertRaisesRegex(JobPrepError, "duplicate asset_id"):
            compile_application_prep(
                job_ref="ats:2026:JOB-X",
                requirements=[
                    {
                        "requirement_id": "cv",
                        "accepted_asset_types": ["cv"],
                        "track": "Data/AI general",
                        "language": "en",
                    }
                ],
                asset_registry=REGISTRY + [dict(REGISTRY[0])],
                as_of="2026-10-07",
            )


if __name__ == "__main__":
    unittest.main()

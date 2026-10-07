from __future__ import annotations

from office_runtime.jobs import JobPrepError, compile_application_prep


REGISTRY = [
    {
        "asset_id": "CV_GENERIC_EN_2026",
        "asset_type": "cv",
        "track": "Data/AI general",
        "language": "en",
        "status": "candidate_needs_review",
        "title": "CV_IGLESIAS.pdf",
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


def test_zs_uses_generic_cv_only_as_review_required_fallback() -> None:
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

    assert packet["ready_for_submission_materially"] is False
    req = packet["requirements"][0]
    assert req["state"] == "review-required"
    assert req["selected_asset"]["asset_id"] == "CV_GENERIC_EN_2026"
    assert req["known_missing_assets"] == ["CV_DATA_SCIENCE_EN"]


def test_fractal_exposes_cv_review_and_cover_letter_reference() -> None:
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
                "accepted_asset_types": ["cover_letter", "cover_letter_reference"],
                "track": "general",
                "language": "en",
                "allow_general_base": True,
            },
        ],
        asset_registry=REGISTRY,
        as_of="2026-10-07",
    )

    states = {item["requirement_id"]: item["state"] for item in packet["requirements"]}
    assert states == {
        "role-specific-cv": "review-required",
        "cover-letter": "draft-from-reference",
    }
    assert packet["ready_for_submission_materially"] is False


def test_unicef_exposes_three_distinct_material_gaps() -> None:
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
                "accepted_asset_types": ["cover_letter", "cover_letter_reference"],
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

    states = {item["requirement_id"]: item["state"] for item in packet["requirements"]}
    assert states["institutional-cv"] == "review-required"
    assert states["cover-letter"] == "draft-from-reference"
    assert states["financial-proposal"] == "missing-known"
    assert packet["ready_for_submission_materially"] is False


def test_approved_exact_track_beats_generic_candidate() -> None:
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
    assert packet["ready_for_submission_materially"] is True
    assert packet["requirements"][0]["selected_asset"]["asset_id"] == "CV_DS_APPROVED"


def test_duplicate_asset_ids_fail_closed() -> None:
    try:
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
    except JobPrepError as exc:
        assert "duplicate asset_id" in str(exc)
    else:
        raise AssertionError("duplicate asset IDs must fail closed")

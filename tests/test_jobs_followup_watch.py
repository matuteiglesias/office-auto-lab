from __future__ import annotations

from office_runtime.jobs import compile_followup_watch


def _action(job_id: str, company: str, action_class: str, urgency: str, follow_state: str, *, deadline=None) -> dict:
    return {
        "job": {
            "id": job_id,
            "company": company,
            "role": "Role",
            "process_status": "active",
            "deadline": deadline,
        },
        "action": {
            "class": action_class,
            "urgency": urgency,
            "next_block": f"Next for {job_id}",
            "stop_condition": f"Stop for {job_id}",
        },
        "follow_up": {
            "state": follow_state,
            "due_on": "2026-10-07" if follow_state == "due" else None,
        },
        "contact": {"primary": {"name": "Recruiter", "email": "r@example.com"} if job_id == "JOB-210" else None},
    }


def test_today_watch_surfaces_telus_and_unicef_only() -> None:
    actions = [
        _action("JOB-209", "BEON.tech", "CLOSE_OR_WAIT_FEEDBACK", "low", "waiting-response"),
        _action("JOB-210", "TELUS Digital", "FOLLOW_UP", "high", "due"),
        _action("JOB-211", "ZS", "PREPARE_APPLICATION", "normal", "blocked-on-application"),
        _action("JOB-213", "UNICEF", "APPLY_NOW", "critical", "blocked-on-application", deadline="2026-10-08"),
    ]
    prep = [
        {
            "job_ref": "ats:2026:JOB-211",
            "ready_for_submission_materially": False,
            "requirements": [{"requirement_id": "cv", "state": "review-required"}],
        },
        {
            "job_ref": "ats:2026:JOB-213",
            "ready_for_submission_materially": False,
            "requirements": [
                {"requirement_id": "cv", "state": "review-required"},
                {"requirement_id": "financial-proposal", "state": "missing-known"},
            ],
        },
    ]

    watch = compile_followup_watch(
        action_packets=actions,
        prep_packets=prep,
        previous_fingerprints={},
        as_of="2026-10-07",
    )

    assert watch["notify"] is True
    assert [item["job_id"] for item in watch["attention"]] == ["JOB-213", "JOB-210"]
    unicef = watch["attention"][0]
    assert unicef["severity"] == "critical"
    assert unicef["reasons"] == ["application-deadline", "application-material-blocker"]
    telus = watch["attention"][1]
    assert telus["reasons"] == ["process-follow-up-due"]
    assert telus["verified_contact"]["email"] == "r@example.com"


def test_unchanged_attention_is_suppressed_by_fingerprint() -> None:
    actions = [_action("JOB-210", "TELUS Digital", "FOLLOW_UP", "high", "due")]
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
    assert first["notify"] is True
    assert second["notify"] is False
    assert second["attention"] == []


def test_material_blocker_without_high_urgency_does_not_nag() -> None:
    actions = [_action("JOB-211", "ZS", "PREPARE_APPLICATION", "normal", "blocked-on-application")]
    prep = [{
        "job_ref": "ats:2026:JOB-211",
        "ready_for_submission_materially": False,
        "requirements": [{"requirement_id": "cv", "state": "review-required"}],
    }]
    watch = compile_followup_watch(
        action_packets=actions,
        prep_packets=prep,
        previous_fingerprints={},
        as_of="2026-10-07",
    )
    assert watch["notify"] is False


def test_changed_state_can_notify_again() -> None:
    actions = [_action("JOB-210", "TELUS Digital", "FOLLOW_UP", "high", "due")]
    first = compile_followup_watch(
        action_packets=actions, prep_packets=[], previous_fingerprints={}, as_of="2026-10-07"
    )
    changed = [_action("JOB-210", "TELUS Digital", "APPLY_NOW", "critical", "blocked-on-application", deadline="2026-10-08")]
    second = compile_followup_watch(
        action_packets=changed,
        prep_packets=[],
        previous_fingerprints=first["fingerprints"],
        as_of="2026-10-08",
    )
    assert second["notify"] is True
    assert second["attention"][0]["reasons"] == ["application-deadline"]
